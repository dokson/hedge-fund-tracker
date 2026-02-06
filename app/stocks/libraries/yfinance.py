from app.stocks.libraries.base_library import FinanceLibrary
from app.utils.console import silence_output
from datetime import date, timedelta
from tenacity import retry, stop_after_attempt, wait_exponential
import logging
import re
import requests
import yfinance as yf

# Silence yfinance logger
logging.getLogger('yfinance').setLevel(logging.CRITICAL)


class YFinance(FinanceLibrary):
    """
    Client for searching stock information using the yfinance library, implementing the FinanceLibrary interface.
    """
    FALLBACK_SUFFIXES = [".TO", ".V"]

    @staticmethod
    def _sanitize_ticker(ticker: str) -> str:
        """
        Sanitizes the ticker for yfinance. Replaces '.' with '-' for share classes (e.g., BRK.B), but preserves '.' for international suffixes (e.g., AAPL.TO).
        """
        if '.' in ticker and not any(ticker.endswith(s) for s in YFinance.FALLBACK_SUFFIXES):
            return ticker.replace('.', '-')
        return ticker


    @staticmethod
    def get_company(cusip: str, **kwargs) -> str | None:
        """
        Searches for a company name for a given ticker using the yfinance library.

        Args:
            cusip (str): The CUSIP of the stock.
            ticker (str): The stock ticker.

        Returns:
            str | None: The company name if found, otherwise None.
        """
        ticker = kwargs.get('ticker')
        if not ticker:
            ticker = YFinance.get_ticker(cusip)
        else:
            ticker = YFinance._sanitize_ticker(ticker)

        try:
            with silence_output():
                stock_info = yf.Ticker(ticker).info
            company_name = stock_info.get('longName') or stock_info.get('shortName', '')
            if company_name:
                return re.sub(r'[.,]', '', company_name)
            print(f"🚨 YFinance: No company found for CUSIP {cusip}.")
        except Exception as e:
            print(f"❌ ERROR: Failed to get company for Ticker {ticker} using YFinance: {e}")
            return None


    @staticmethod
    def get_ticker(cusip: str, **kwargs) -> str | None:
        """
        Searches for a ticker for a given CUSIP by querying the Yahoo Finance search API.

        Args:
            cusip (str): The CUSIP of the stock.

        Returns:
            str | None: The ticker symbol if found, otherwise None.
        """
        url = f"https://query1.finance.yahoo.com/v1/finance/search?q={cusip}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

            quotes = data.get('quotes', [])
            for quote in quotes:
                return quote['symbol']
            print(f"🚨 YFinance: No ticker found for CUSIP {cusip}.")
        except (requests.RequestException, ValueError) as e:
            print(f"❌ ERROR: Failed to get ticker for CUSIP {cusip} using YFinance: {e}")
            return None


    @staticmethod
    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        before_sleep=lambda retry_state: print(f"⏳ Retrying get_avg_price for {retry_state.args[0]} (attempt #{retry_state.attempt_number})...")
    )
    def get_avg_price(ticker: str, date: date) -> float | None:
        """
        Gets the average daily price for a ticker on a specific date using the yfinance library.
        The average price is calculated as (High + Low) / 2.
        If no data is found for the specified date (e.g., delisting), tries with current_price.

        Args:
            ticker (str): The stock ticker.
            date (date): The date for which to fetch the price.

        Returns:
            float | None: The average price if found, otherwise None.
        """
        def _get_single_avg_price(t: str) -> float | None:
            search_ticker = YFinance._sanitize_ticker(t)
            # 'end' parameter is exclusive: To get a single day, we need the next day as the end.
            with silence_output():
                price_data = yf.download(tickers=search_ticker, start=date, end=date+timedelta(days=1), auto_adjust=False, progress=False)
            
            if not price_data.empty:
                return round((price_data['High'].iloc[0].item() + price_data['Low'].iloc[0].item()) / 2, 2)
            return None

        try:
            # Try original ticker first
            price = _get_single_avg_price(ticker)
            if price is not None:
                return price
            
            # Fallback for international tickers (e.g., TSX, TSXV)
            # Only attempt fallback if the ticker doesn't already have a separator
            if "." not in ticker and "-" not in ticker:
                for suffix in YFinance.FALLBACK_SUFFIXES:
                    try:
                        fallback_ticker = ticker + suffix
                        print(f"⏳ YFinance: Trying fallback {fallback_ticker} for {ticker}...")
                        price = _get_single_avg_price(fallback_ticker)
                        if price is not None:
                            return price
                    except:
                        continue

            print(f"🚨 Using latest available price for {ticker} (requested date {date} not available)")
            return YFinance.get_current_price(ticker)
        except Exception as e:
            print(f"❌ ERROR: Failed to get price for Ticker {ticker} on {date} using YFinance: {e}")
            raise e


    @staticmethod
    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        before_sleep=lambda retry_state: print(f"⏳ Retrying get_current_price for {retry_state.args[0]} (attempt #{retry_state.attempt_number})...")
    )
    def get_current_price(ticker: str) -> float | None:
        """
        Gets the current market price for a ticker using the yfinance library.

        Args:
            ticker (str): The stock ticker.

        Returns:
            float | None: The current price if found, otherwise None.
        """
        try:
            search_ticker = YFinance._sanitize_ticker(ticker)
            with silence_output():
                stock = yf.Ticker(search_ticker)
                price = stock.info.get('currentPrice')
            
            # Fallback for international tickers (e.g., TSX, TSXV)
            if price is None and "." not in ticker and "-" not in ticker:
                for suffix in YFinance.FALLBACK_SUFFIXES:
                    try:
                        fallback_ticker = ticker + suffix
                        print(f"⏳ YFinance: Trying current price fallback {fallback_ticker} for {ticker}...")
                        with silence_output():
                            price = yf.Ticker(fallback_ticker).info.get('currentPrice')
                        if price is not None:
                            break
                    except:
                        continue

            return float(price) if price is not None else None
        except Exception as e:
            print(f"❌ ERROR: Failed to get current price for Ticker {ticker} using YFinance: {e}")
            raise e


    @staticmethod
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        before_sleep=lambda retry_state: print(f"⏳ Retrying get_stocks_info for {retry_state.args[0]} (attempt #{retry_state.attempt_number})...")
    )
    def get_stocks_info(tickers: list[str]) -> dict[str, dict]:
        """
        Gets the current market prices and sector information for a list of tickers efficiently.

        Args:
            tickers (list[str]): A list of stock tickers.

        Returns:
            dict[str, dict]: A dictionary mapping tickers to their info (price, sector).
                            Example: {'AAPL': {'price': 150.25, 'sector': 'Technology'}}
        """
        if not tickers:
            return {}
        
        # Create a mapping between sanitized and original tickers
        ticker_map = {YFinance._sanitize_ticker(t): t for t in tickers}
        sanitized_tickers = list(ticker_map.keys())

        stocks_info = {}

        try:
            with silence_output():
                data = yf.download(tickers=sanitized_tickers, period='1d', interval='1m', group_by='ticker', auto_adjust=False, progress=False)

            for sanitized, original in ticker_map.items():
                try:
                    if len(sanitized_tickers) == 1:
                        ticker_data = data
                    else:
                        ticker_data = data[sanitized]

                    if not ticker_data.empty:
                        price = ticker_data['Close'].dropna().iloc[-1].item()
                        stocks_info[original] = {'price': float(price), 'sector': None}
                except Exception:
                    continue

            # Get sector info for all tickers (both successful and failed price fetches)
            for sanitized, original in ticker_map.items():
                try:
                    with silence_output():
                        stock = yf.Ticker(sanitized)
                        sector = stock.info.get('sector') or stock.info.get('industry')

                    if original in stocks_info:
                        stocks_info[original]['sector'] = sector
                    else:
                        # Price fallback
                        print(f"⏳ Getting current price for {original}...")
                        price = YFinance.get_current_price(original)
                        if price:
                            stocks_info[original] = {'price': price, 'sector': sector}
                except Exception:
                    continue

            return stocks_info
        except Exception as e:
            print(f"❌ ERROR: Failed to get stock info using YFinance: {e}")
            raise e


    @staticmethod
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        before_sleep=lambda retry_state: print(f"⏳ Retrying get_sector_tickers for {retry_state.args[0]} (attempt #{retry_state.attempt_number})...")
    )
    def get_sector_tickers(sector_key: str, limit: int = None) -> list[dict]:
        """
        Gets a list of tickers for companies in a specific sector.

        Args:
            sector_key (str): The sector key (e.g., 'technology', 'healthcare', 'financial-services').
            limit (int, optional): Maximum number of tickers to return. If None, returns all available.

        Returns:
            list[dict]: A list of dictionaries with ticker info.
                       Example: [{'symbol': 'AAPL', 'name': 'Apple Inc.', 'weight': 0.15}, ...]
        """
        try:
            with silence_output():
                sector = yf.Sector(sector_key)
                top_companies = sector.top_companies

            if top_companies is None or top_companies.empty:
                # Raise error to trigger @retry
                raise ValueError(f"🚨 No companies found for sector '{sector_key}'")

            companies = []
            for _, row in top_companies.iterrows():
                company_info = {
                    'symbol': row.get('symbol', ''),
                    'name': row.get('name', ''),
                    'weight': row.get('weight', 0.0) if 'weight' in row else None
                }
                companies.append(company_info)

                if limit and len(companies) >= limit:
                    break

            return companies
        except Exception as e:
            print(f"❌ ERROR: Failed to get tickers for sector '{sector_key}': {e}")
            raise e

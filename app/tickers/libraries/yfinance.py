from app.tickers.libraries.base_library import FinanceLibrary
from datetime import date, timedelta
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import re
import requests
import yfinance as yf


class YFinance(FinanceLibrary):
    """
    Client for searching stock information using the yfinance library, implementing the FinanceLibrary interface.
    """
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

        try:
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
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        retry=retry_if_exception_type((requests.exceptions.Timeout, TimeoutError)),
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
        try:
            # 'end' parameter is exclusive: To get a single day, we need the next day as the end.
            price_data = yf.download(tickers=ticker, start=date, end=date+timedelta(days=1), auto_adjust=False, progress=False)
            if not price_data.empty:
                price = round((price_data['High'].iloc[0].item() + price_data['Low'].iloc[0].item()) / 2, 2)
                return price
            else:
                print(f"🚨 Using latest available price for {ticker} (requested date {date} not available)")
                return YFinance.get_current_price(ticker)
        except Exception as e:
            print(f"❌ ERROR: Failed to get price for Ticker {ticker} on {date} using YFinance: {e}")
            return None


    @staticmethod
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        retry=retry_if_exception_type((requests.exceptions.Timeout, TimeoutError)),
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
            stock = yf.Ticker(ticker)
            price = stock.info.get('currentPrice')
            return float(price) if price is not None else None
        except Exception as e:
            print(f"❌ ERROR: Failed to get current price for Ticker {ticker} using YFinance: {e}")
            return None

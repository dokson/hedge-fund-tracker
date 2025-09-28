from datetime import date, timedelta
import re
import requests
import yfinance as yf


class YFinance:
    """
    Client for searching stock information using the yfinance library.
    This class provides a method to find company names based on tickers.
    """

    @staticmethod
    def get_company(ticker: str) -> str | None:
        """
        Searches for a company name for a given ticker using the yfinance library.

        Args:
            ticker (str): The stock ticker.

        Returns:
            str | None: The company name if found, otherwise None.
        """
        try:
            stock_info = yf.Ticker(ticker).info
            company_name = stock_info.get('longName') or stock_info.get('shortName', '')
            return re.sub(r'[.,]', '', company_name) if company_name else None
        except Exception as e:
            print(f"❌ ERROR: Failed to get company for Ticker {ticker} using YFinance: {e}")
            return None


    @staticmethod
    def get_ticker(cusip: str) -> str | None:
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
        except (requests.RequestException, ValueError) as e:
            print(f"❌ ERROR: Failed to get ticker for CUSIP {cusip} using YFinance: {e}")
            return None


    @staticmethod
    def get_avg_price(ticker: str, date: date) -> float | None:
        """
        Gets the average daily price for a ticker on a specific date using the yfinance library.
        The average price is calculated as (High + Low) / 2.

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
                return round((price_data['High'].iloc[0].item() + price_data['Low'].iloc[0].item()) / 2, 2)
        except Exception as e:
            print(f"❌ ERROR: Failed to get price for Ticker {ticker} on {date} using YFinance: {e}")
            return None

import yfinance as yf
import requests

TICKER_NOT_FOUND_MSG = 'No data found, symbol may be delisted'

class YFinance:
    """
    Client for searching stock information using the yfinance library.
    This class provides a method to find company names based on tickers.
    """
    _COMPANY_CACHE = {}
    _TICKER_CACHE = {}


    @staticmethod
    def get_company(ticker: str) -> str | None:
        """
        Searches for a company name for a given ticker using yfinance.
        It uses a simple in-memory cache to avoid redundant API calls.

        Args:
            ticker (str): The stock ticker.

        Returns:
            str: The company name if found, otherwise an empty string.
        """
        if ticker in YFinance._COMPANY_CACHE:
            return YFinance._COMPANY_CACHE[ticker]

        try:
            stock_info = yf.Ticker(ticker).info
            company_name = stock_info.get('longName') or stock_info.get('shortName', '')
            YFinance._COMPANY_CACHE[ticker] = company_name
            return company_name
        except Exception as e:
            print(f"❌ ERROR: Failed to get company for Ticker {ticker} using YFinance: {e}")
            return None


    @staticmethod
    def get_ticker(cusip: str) -> str | None:
        """
        Searches for a ticker for a given CUSIP by querying the Yahoo Finance search API.
        It uses a simple in-memory cache to avoid redundant API calls.

        Args:
            cusip (str): The CUSIP of the stock.

        Returns:
            str | None: The ticker symbol if found, otherwise None.
        """
        if cusip in YFinance._TICKER_CACHE:
            return YFinance._TICKER_CACHE[cusip]

        url = f"https://query1.finance.yahoo.com/v1/finance/search?q={cusip}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

            quotes = data.get('quotes', [])
            for quote in quotes:
                YFinance._TICKER_CACHE[cusip] = quote['symbol']
                return quote['symbol']
        except (requests.RequestException, ValueError) as e:
            print(f"❌ ERROR: Failed to get ticker for CUSIP {cusip} using YFinance: {e}")
        
        YFinance._TICKER_CACHE[cusip] = None
        return None

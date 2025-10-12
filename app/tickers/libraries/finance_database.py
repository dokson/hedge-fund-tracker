
from app.tickers.libraries.base_library import FinanceLibrary
from app.utils.github import open_issue
import financedatabase as fd
import random
import string
import pandas as pd


class FinanceDatabase(FinanceLibrary):
    """
    Client for searching stock information using the financedatabase library.
    This class provides static methods to find tickers and company names based on CUSIPs, encapsulating the logic for handling search results.
    """
    @staticmethod
    def _search_and_sort(**kwargs) -> pd.DataFrame | None:
        """
        Searches for an equity and returns a DataFrame sorted by ticker length.

        Args:
            **search_kwargs: Keyword arguments for the search (e.g., cusip='...', index='...').

        Returns:
            pd.DataFrame | None: A sorted DataFrame if results are found, otherwise None.
        """
        result = fd.Equities().search(**kwargs).copy()
        if not result.empty:
            if 'index' in kwargs:
                return result[result.index == kwargs['index']]
            else:
                result['ticker_length'] = [len(idx) for idx in result.index]
                return result.sort_values(by='ticker_length')
        return None


    @staticmethod
    def get_ticker(cusip: str, **kwargs) -> str | None:
        """
        Searches for a ticker for a given CUSIP using financedatabase.

        If multiple tickers are found, it returns the shortest one, which is often the primary ticker.

        Args:
            cusip (str): The CUSIP of the stock.

        Returns:
            str | None: The ticker symbol if found, otherwise None.
        """
        result = FinanceDatabase._search_and_sort(cusip=cusip)

        if result is not None:
            return result.index[0]

        print(f"⚠️\u3000Finance Database: No ticker found for CUSIP {cusip}")
        return None


    @staticmethod
    def get_company(cusip: str, **kwargs) -> str | None:
        """
        Searches for a company name for a given CUSIP using financedatabase.

        If multiple results are found, it returns the name associated with the shortest ticker.

        Args:
            cusip (str): The CUSIP of the stock.

        Returns:
            str: The company name if found, otherwise an empty string.
        """
        result = FinanceDatabase._search_and_sort(cusip=cusip)

        if result is not None:
            return result.iloc[0]['name'].title()

        print(f"⚠️\u3000Finance Database: No company found for CUSIP {cusip}")

        subject = f"No company found for CUSIP '{cusip}'"
        body = f"Could not find any company for the CUSIP **{cusip}**."
        open_issue(subject, body)
        return None


    @staticmethod
    def get_cusip(ticker: str) -> str | None:
        """
        Searches for a CUSIP for a given ticker using financedatabase.

        Args:
            ticker (str): The stock ticker to search for.

        Returns:
            str | None: The CUSIP if found, otherwise None.
        """
        result = FinanceDatabase._search_and_sort(index=ticker)
        
        if result is not None:
            return result.iloc[0]['cusip']
    
        print(f"⚠️\u3000Finance Database: No CUSIP found for ticker {ticker}")

        subject = f"No CUSIP found for ticker '{ticker}'"
        body = f"Could not find any CUSIP for the ticker **{ticker}**."
        open_issue(subject, body)
        # A random CUSIP is generated to prevent the filing compilation from failing.
        return f"N/A {''.join(random.choices(string.ascii_uppercase + string.digits, k=5))}"

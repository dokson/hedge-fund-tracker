import financedatabase as fd
import pandas as pd


class FinanceDatabase:
    """
    Client for searching stock information using the financedatabase library.
    This class provides static methods to find tickers and company names based on CUSIPs, encapsulating the logic for handling search results.
    """
    @staticmethod
    def _search_and_sort(cusip: str) -> pd.DataFrame | None:
        """
        Searches for a CUSIP and returns a DataFrame sorted by ticker length.

        Args:
            cusip (str): The CUSIP to search for.

        Returns:
            pd.DataFrame | None: A sorted DataFrame if results are found, otherwise None.
        """
        result = fd.Equities().search(cusip=cusip)
        if not result.empty:
            result['ticker_length'] = [len(idx) for idx in result.index]
            return result.sort_values(by='ticker_length')
        return None


    @staticmethod
    def get_ticker(cusip: str) -> str | None:
        """
        Searches for a ticker for a given CUSIP using financedatabase.

        If multiple tickers are found, it returns the shortest one, which is often the primary ticker.

        Args:
            cusip (str): The CUSIP of the stock.

        Returns:
            str | None: The ticker symbol if found, otherwise None.
        """
        sorted_result = FinanceDatabase._search_and_sort(cusip)

        if sorted_result is not None:
            return sorted_result.index[0]

        print(f"⚠️\u3000Finance Database: No ticker found for CUSIP {cusip}")
        return None


    @staticmethod
    def get_company(cusip: str) -> str:
        """
        Searches for a company name for a given CUSIP using financedatabase.

        If multiple results are found, it returns the name associated with the shortest ticker.

        Args:
            cusip (str): The CUSIP of the stock.

        Returns:
            str: The company name if found, otherwise an empty string.
        """
        sorted_result = FinanceDatabase._search_and_sort(cusip)

        if sorted_result is not None:
            return sorted_result.iloc[0]['name']

        print(f"⚠️\u3000Finance Database: No company found for CUSIP {cusip}")
        return ''

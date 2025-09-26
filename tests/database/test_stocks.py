import unittest
from app.utils.database import load_stocks


class TestStocksDatabase(unittest.TestCase):
    def test_no_duplicate_tickers_with_different_companies(self):
        """
        Verifies that each ticker corresponds to only one unique company name in the stocks.csv file.
        If a ticker is found with multiple different company descriptions, the test will fail.
        """
        stocks_df = load_stocks().reset_index()

        # Group by Ticker and count the number of unique Company names
        ticker_companies = stocks_df.groupby('Ticker')['Company'].nunique()

        # Filter for tickers that have more than one unique company name
        inconsistent_tickers = ticker_companies[ticker_companies > 1]

        if not inconsistent_tickers.empty:
            offending_tickers_list = inconsistent_tickers.index.tolist()
            offending_records = stocks_df[stocks_df['Ticker'].isin(offending_tickers_list)].sort_values(by=['Ticker', 'Company'])

            error_message = (
                f"Found {len(inconsistent_tickers)} tickers with multiple different company descriptions.\n"
                "Please resolve the inconsistencies for the following tickers:\n\n"
                f"{offending_records.to_string(index=False)}"
            )
            self.fail(error_message)

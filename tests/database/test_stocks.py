from app.utils.database import DB_FOLDER, LATEST_SCHEDULE_FILINGS_FILE, get_all_quarters, load_quarterly_data, load_stocks
import unittest
import pandas as pd


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


    def test_orphan_cusips(self):
        """
        Identifies orphan CUSIPs that belong to a Ticker with multiple CUSIPs in stocks.csv.
        An orphan CUSIP is one that exists in stocks.csv but not in any filing. This test helps pinpoint and clean up obsolete CUSIPs.
        """
        stocks_df = load_stocks().reset_index()
        all_stock_cusips = set(stocks_df['CUSIP'])
        all_filing_cusips = set()

        # 1. Collect all CUSIPs from all quarterly reports
        for quarter in get_all_quarters():
            quarter_df = load_quarterly_data(quarter)
            if not quarter_df.empty:
                all_filing_cusips.update(quarter_df['CUSIP'].dropna().unique())

        # 2. Collect all CUSIPs from non-quarterly filings
        try:
            non_quarterly_path = f"{DB_FOLDER}/{LATEST_SCHEDULE_FILINGS_FILE}"
            non_quarterly_cusips_df = pd.read_csv(non_quarterly_path, usecols=['CUSIP'], dtype={'CUSIP': str})
            all_filing_cusips.update(non_quarterly_cusips_df['CUSIP'].dropna().unique())
        except FileNotFoundError:
            pass  # If the file doesn't exist, there's nothing to add.

        # 3. Find orphan CUSIPs (present in stocks.csv but not in any filings)
        orphan_cusips = all_stock_cusips - all_filing_cusips

        if not orphan_cusips:
            return

        # 4. Filter orphans to find only those belonging to Tickers with more than one CUSIP
        orphan_df = stocks_df[stocks_df['CUSIP'].isin(orphan_cusips)]
        ticker_cusip_counts = stocks_df.groupby('Ticker')['CUSIP'].nunique()
        tickers_with_multiple_cusips = ticker_cusip_counts[ticker_cusip_counts > 1].index

        # Isolate orphan CUSIPs that belong to these tickers
        final_orphans_df = orphan_df[orphan_df['Ticker'].isin(tickers_with_multiple_cusips)]

        if not final_orphans_df.empty:
            sorted_orphans_df = final_orphans_df.sort_values(by=['Ticker', 'CUSIP'])
            error_message = (
                f"Found {len(final_orphans_df)} orphan CUSIPs for tickers with multiple CUSIP entries in stocks.csv.\n"
                "These CUSIPs are not found in any filings and are likely outdated. Review and consider removing them.\n\n"
                f"{sorted_orphans_df.to_string(index=False)}"
            )
            self.fail(error_message)

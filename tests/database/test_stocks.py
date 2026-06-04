from app.database import DB_FOLDER, LATEST_SCHEDULE_FILINGS_FILE, get_all_quarters, load_quarterly_data, load_sector_hierarchy, load_stocks
import pandas as pd
import unittest


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
        non_quarterly_path = f"{DB_FOLDER}/{LATEST_SCHEDULE_FILINGS_FILE}"
        non_quarterly_cusips_df = pd.read_csv(non_quarterly_path, usecols=['CUSIP'], dtype={'CUSIP': str})
        all_filing_cusips.update(non_quarterly_cusips_df['CUSIP'].dropna().unique())

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


    def test_all_report_cusips_in_stocks_master(self):
        """
        Verifies that all CUSIPs found in quarterly and non-quarterly filings are present in stocks.csv.
        If any CUSIP from a filing is not in stocks.csv, the test will fail, indicating a data integrity issue.
        """
        stocks_df = load_stocks().reset_index()
        master_cusips = set(stocks_df['CUSIP'])
        all_filing_cusips = set()

        # 1. Collect all CUSIPs from all quarterly reports
        for quarter in get_all_quarters():
            quarter_df = load_quarterly_data(quarter)
            if not quarter_df.empty:
                all_filing_cusips.update(quarter_df['CUSIP'].dropna().unique())

        # 2. Collect all CUSIPs from non-quarterly filings
        non_quarterly_path = f"{DB_FOLDER}/{LATEST_SCHEDULE_FILINGS_FILE}"
        non_quarterly_cusips_df = pd.read_csv(non_quarterly_path, usecols=['CUSIP'], dtype={'CUSIP': str})
        all_filing_cusips.update(non_quarterly_cusips_df['CUSIP'].dropna().unique())

        # 3. Find CUSIPs that are in reports but NOT in stocks.csv
        missing_cusips_in_master = all_filing_cusips - master_cusips

        if missing_cusips_in_master:
            # Create a DataFrame for consistent output formatting
            missing_df = pd.DataFrame({'CUSIP': sorted(list(missing_cusips_in_master))})
            error_message = (
                f"Found {len(missing_cusips_in_master)} CUSIPs in quarterly or non-quarterly filings "
                f"that are NOT present in stocks.csv.\n"
                "These CUSIPs should be added to stocks.csv to maintain data integrity.\n\n"
                f"{missing_df.to_string(index=False)}"
            )
            self.fail(error_message)


    def test_stocks_file_is_sorted(self):
        """
        Verifies that stocks.csv is sorted by 'Ticker' and then by 'CUSIP'.
        This ensures that the file is consistently organized, which is important for readability and version control.
        """
        stocks_df = load_stocks().reset_index()

        # Create a sorted version of the DataFrame
        sorted_df = stocks_df.sort_values(by=['Ticker', 'CUSIP'])

        # Check if the original DataFrame is identical to the sorted one
        if not stocks_df.equals(sorted_df):
            error_message = (
                f"The stock.csv file is not sorted correctly by 'Ticker'.\n"
                "Please run the database updater with option '0. Exit' to sort the file."
            )
            self.fail(error_message)


    def test_industries_present_in_sector_hierarchy(self):
        """
        Every non-empty Industry in stocks.csv must appear exactly in
        database/sector_hierarchy.csv. The Sector is derived via that mapping —
        an industry missing from the hierarchy would silently lose its sector
        and break the dashboard's sector roll-up.
        """
        stocks_df = load_stocks().reset_index()
        hierarchy_df = load_sector_hierarchy()

        allowed = set(hierarchy_df["Industry"])
        populated = stocks_df[stocks_df["Industry"] != ""]
        invalid = populated[~populated["Industry"].isin(allowed)]

        if not invalid.empty:
            unknown = sorted(invalid["Industry"].unique())
            sample = invalid[["CUSIP", "Ticker", "Company", "Industry"]].head(20)
            error_message = (
                f"Found {len(invalid)} rows ({len(unknown)} distinct industries) whose "
                "Industry value is missing from database/sector_hierarchy.csv:\n\n"
                f"Unknown industries: {unknown}\n\n"
                "Sample offending rows:\n"
                f"{sample.to_string(index=False)}\n\n"
                "Fix by either correcting the Industry in stocks.csv or by "
                "adding the missing (Sector, Industry) pair to sector_hierarchy.csv."
            )
            self.fail(error_message)


    def test_same_company_has_consistent_industry(self):
        """
        When multiple CUSIPs/tickers share the same Company name (e.g. common
        stock + its warrant, or multiple share classes of the same issuer),
        their Industry must agree. A warrant cannot be `Shell Companies` while
        the underlying common stock is `Software - Application` — they describe
        the same business.
        """
        stocks_df = load_stocks().reset_index()
        populated = stocks_df[stocks_df["Industry"] != ""]
        # For each Company, collect the distinct industries assigned to it.
        industries_per_company = populated.groupby("Company")["Industry"].agg(
            lambda s: sorted(set(s))
        )
        inconsistent = industries_per_company[industries_per_company.map(len) > 1]

        if not inconsistent.empty:
            sample_lines = []
            for company, industries in inconsistent.head(15).items():
                tickers = sorted(
                    populated.loc[populated["Company"] == company, "Ticker"].tolist()
                )
                sample_lines.append(f"  {company} | tickers={tickers} | industries={industries}")

            error_message = (
                f"Found {len(inconsistent)} companies whose rows in stocks.csv disagree on Industry.\n"
                "Each company name must map to a single Industry across all its CUSIPs.\n\n"
                "Sample offending companies:\n" + "\n".join(sample_lines)
            )
            self.fail(error_message)


    def test_no_truncated_names(self):
        """
        Checks for company names in stocks.csv that appear to be truncated.
        Fails if any company name ends with suspicious suffixes indicating truncation.
        """
        stocks_df = load_stocks().reset_index()

        # List of suffixes that often indicate truncation
        suspicious_suffixes = (
            " H", "Accep", "Acqu", "Acquistn", "Act", "Amer", "Argenta", "Brasileir", "Buenaventu", "Ca", "Cent", "Chesapea", "Cnty",
            "Comm", "Comms", "Companie", "Dynamic", "Elec", "Fragra", "Gen", "Genera", "Grou", "Grwt", "Hig", "Inco", "Indl", "Infr",
            "Infrastructu", "Infrastructure", "Inm", "Ins", "Internat", "Lendi", "Limite", "Mach", "Machs", "Mfg", "Nat", "Northn",
            "Ohio", "Op", "Opp", "Par", "Pare", "Partne", "Partner", "Pete", "Petro", "Real", "Resh", "Rty", "Soluti", "Solutio",
            "Solution", "Southn", "Strate", "Suppo", "Svgs", "Svsc", "Technologs", "Therapeuti", "TrueShar", "Vang", "Vy", "Wash"
        )

        # Filter rows where the Company column ends with one of the suffixes
        truncated = stocks_df[stocks_df['Company'].str.endswith(suspicious_suffixes, na=False)]

        if not truncated.empty:
            error_message = (
                f"Found {len(truncated)} company names that appear to be truncated.\n"
                "Please fix the following names in stocks.csv:\n\n"
                f"{truncated[['Ticker', 'Company']].to_string(index=False)}"
            )
            self.fail(error_message)

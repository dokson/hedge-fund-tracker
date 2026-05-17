import contextlib
import io
import shutil
import tempfile
import threading
import time
import unittest
import unittest.mock
from pathlib import Path

import pandas as pd

from app.utils.database import (
    GICS_HIERARCHY_FILE,
    HEDGE_FUNDS_FILE,
    LATEST_SCHEDULE_FILINGS_FILE,
    MODELS_FILE,
    STOCKS_FILE,
    count_funds_in_quarter,
    delete_fund_from_database,
    find_cusips_for_ticker,
    get_all_quarters,
    get_last_quarter,
    get_last_quarter_for_fund,
    get_most_recent_quarter,
    get_quarters_for_fund,
    load_excluded_hedge_funds,
    load_fund_holdings,
    load_gics_hierarchy,
    load_hedge_funds,
    load_models,
    load_non_quarterly_data,
    load_stocks,
    restore_fund_to_database,
    save_stock,
    sort_excluded_hedge_funds,
    sort_hedge_funds,
    sort_stocks,
    update_ticker,
)


class TestDatabase(unittest.TestCase):
    def setUp(self):
        """
        Set up a temporary database directory and files for testing.
        This runs before each test.

        Uses tempfile.mkdtemp so parallel test runs don't collide on a shared
        path and so a crashed test doesn't leave residue inside the repo.
        """
        self.test_db_folder = tempfile.mkdtemp(prefix="hft_test_db_")
        test_db_path = Path(self.test_db_folder)

        # Create dummy quarter directories and files
        (test_db_path / "2025Q1").mkdir(parents=True, exist_ok=True)
        (test_db_path / "2024Q4").mkdir(parents=True, exist_ok=True)
        (test_db_path / "not_a_quarter").mkdir(parents=True, exist_ok=True)

        with (test_db_path / "2025Q1" / "Fund_A.csv").open("w", newline="") as f:
            f.write("CUSIP,Ticker,Value,Shares\n123,TICKA,100,10\nTotal,Total,100,10\n")
        with (test_db_path / "2025Q1" / "Fund_B.csv").open("w", newline="") as f:
            f.write("CUSIP,Ticker,Value,Shares\n456,TICKB,200,20\n")
        with (test_db_path / "2024Q4" / "Fund_A.csv").open("w", newline="") as f:
            f.write("CUSIP,Ticker,Value,Shares\n123,TICKA,80,10\n")

        # Create dummy main db files
        with (test_db_path / HEDGE_FUNDS_FILE).open("w", newline="") as f:
            f.write(
                "CIK,Fund,Manager,Denomination,CIKs,URL\n"
                "001,Fund A,Manager A,Denom A,,https://fund-a.example.com/\n"
            )

        with (test_db_path / MODELS_FILE).open("w", newline="") as f:
            f.write("ID,Description,Client\nmodel-1,Google Model,Google\n")

        with (test_db_path / STOCKS_FILE).open("w", newline="") as f:
            f.write("CUSIP,Ticker,Company\n123,TICKA,Company A\n456,TICKB,Company B\n")

        with (test_db_path / LATEST_SCHEDULE_FILINGS_FILE).open("w", newline="") as f:
            f.write("Fund,Ticker,CUSIP,Date,Filing_Date\nFund A,TICKA,123,2025-01-01,2025-01-01\n")

        (test_db_path / "GICS").mkdir(parents=True, exist_ok=True)
        with (test_db_path / GICS_HIERARCHY_FILE).open("w", newline="") as f:
            f.write("Sector,Industry\nTech,Software\n")

        # Patch the DB_FOLDER constant to use the test directory
        self.patcher = unittest.mock.patch("app.utils.database.DB_FOLDER", self.test_db_folder)
        self.patcher.start()

    def test_get_all_quarters(self):
        """
        Returns only valid quarter directories, sorted in descending order, excluding non-quarter folders.
        """
        self.assertEqual(get_all_quarters(), ["2025Q1", "2024Q4"])

    def test_get_last_quarter(self):
        """
        Returns the most recent quarter folder name.
        """
        self.assertEqual(get_last_quarter(), "2025Q1")

    def test_count_funds_in_quarter(self):
        """
        Returns the count of CSV files in a given quarter folder; 0 for non-existent quarters.
        """
        cases = [("2025Q1", 2), ("2023Q1", 0)]
        for quarter, expected in cases:
            with self.subTest(quarter=quarter):
                self.assertEqual(count_funds_in_quarter(quarter), expected)

    def test_get_last_quarter_for_fund(self):
        """
        Returns the most recent quarter with data for a fund; None if no data found.
        """
        cases = [("Fund A", "2025Q1"), ("Fund C", None)]
        for fund, expected in cases:
            with self.subTest(fund=fund):
                self.assertEqual(get_last_quarter_for_fund(fund), expected)

    def test_get_quarters_for_fund(self):
        """
        Returns all quarters where a fund has data, in descending order.
        """
        cases = [
            ("Fund A", ["2025Q1", "2024Q4"]),
            ("Fund B", ["2025Q1"]),
            ("Fund C", []),
        ]
        for fund, expected in cases:
            with self.subTest(fund=fund):
                self.assertEqual(get_quarters_for_fund(fund), expected)

    def test_get_most_recent_quarter(self):
        """
        Returns the most recent quarter containing a holding for the given ticker; None if unknown.
        """
        cases = [
            ("TICKA", "2025Q1"),
            ("TICKB", "2025Q1"),
            ("UNKNOWN", None),
        ]
        for ticker, expected in cases:
            with self.subTest(ticker=ticker):
                self.assertEqual(get_most_recent_quarter(ticker), expected)

    def test_load_fund_holdings(self):
        """
        Loads holdings excluding the 'Total' row and computes Reported_Price as Value/Shares.
        """
        df = load_fund_holdings("Fund A", "2025Q1")
        self.assertEqual(len(df), 1)  # Total row excluded
        self.assertIn("Reported_Price", df.columns)
        self.assertEqual(df.iloc[0]["Reported_Price"], 10.0)

    def test_load_hedge_funds(self):
        """
        Parses hedge_funds.csv into a list of fund dicts, including the URL column.
        """
        funds = load_hedge_funds()
        self.assertEqual(len(funds), 1)
        self.assertEqual(funds[0]["Fund"], "Fund A")
        self.assertEqual(funds[0]["URL"], "https://fund-a.example.com/")

    def test_load_models(self):
        """
        Parses models.csv into a list of model dicts.
        """
        models = load_models()
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0]["ID"], "model-1")

    def test_load_non_quarterly_data(self):
        """
        Loads non-quarterly filings (13D/G, Form 4) from the CSV file.
        """
        df = load_non_quarterly_data()
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["Ticker"], "TICKA")

    def test_load_gics_hierarchy(self):
        """
        Loads the GICS classification hierarchy from CSV.
        """
        df = load_gics_hierarchy()
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["Sector"], "Tech")

    def test_save_stock_and_sort(self):
        """
        Saves a new stock to the database and verifies it appears after sort.
        """
        save_stock("789", "TICKC", "Company C")
        sort_stocks(str(Path(self.test_db_folder) / STOCKS_FILE))
        df = load_stocks()
        self.assertIn("789", df.index)
        self.assertEqual(df.loc["789", "Ticker"], "TICKC")

    def test_save_stock_strips_whitespace(self):
        """
        Strips leading/trailing whitespace from all fields when saving a stock.
        """
        save_stock(" 999 ", " TRIM ", " Trimmed Company ")
        sort_stocks(str(Path(self.test_db_folder) / STOCKS_FILE))
        df = load_stocks()
        self.assertIn("999", df.index)
        self.assertEqual(df.loc["999", "Ticker"], "TRIM")
        self.assertEqual(df.loc["999", "Company"], "Trimmed Company")

    def test_sort_hedge_funds_alphabetical(self):
        """
        Sorts hedge_funds.csv alphabetically by Fund name (case-insensitive).
        """
        hf_path = Path(self.test_db_folder) / HEDGE_FUNDS_FILE
        with hf_path.open("w", newline="") as f:
            f.write(
                "CIK,Fund,Manager,Denomination,CIKs,URL\n"
                "003,charlie,Mgr C,Denom C,,https://c.example.com/\n"
                "001,Alpha,Mgr A,Denom A,,https://a.example.com/\n"
                "002,Bravo,Mgr B,Denom B,,https://b.example.com/\n"
            )
        sort_hedge_funds(str(hf_path))
        df = pd.read_csv(hf_path, dtype=str, keep_default_na=False)
        self.assertEqual(list(df["Fund"]), ["Alpha", "Bravo", "charlie"])

    def test_sort_excluded_hedge_funds_preserves_top(self):
        """
        Keeps the first README_DISPLAY_LIMIT rows in place and sorts the rest alphabetically.
        """
        from app.utils.database import EXCLUDED_HEDGE_FUNDS_FILE
        from app.utils.readme import README_DISPLAY_LIMIT

        ex_path = Path(self.test_db_folder) / EXCLUDED_HEDGE_FUNDS_FILE
        # Top N curated (kept in given order) + 3 unsorted tail rows
        rows = ["CIK,Fund,Manager,Denomination,CIKs,URL"]
        top_names = [f"Top_{i:03d}" for i in range(README_DISPLAY_LIMIT)]
        for i, n in enumerate(top_names):
            rows.append(f"{i:04d},{n},Mgr,Denom,,https://x.example.com/")
        rows.append("9001,zeta,Mgr Z,Denom Z,,https://z.example.com/")
        rows.append("9002,alpha,Mgr A,Denom A,,https://a.example.com/")
        rows.append("9003,Mike,Mgr M,Denom M,,https://m.example.com/")
        with ex_path.open("w", newline="") as f:
            f.write("\n".join(rows) + "\n")

        sort_excluded_hedge_funds(str(ex_path))
        df = pd.read_csv(ex_path, dtype=str, keep_default_na=False)

        # Top N preserved in original order
        self.assertEqual(list(df["Fund"].iloc[:README_DISPLAY_LIMIT]), top_names)
        # Tail sorted alphabetically (case-insensitive)
        self.assertEqual(list(df["Fund"].iloc[README_DISPLAY_LIMIT:]), ["alpha", "Mike", "zeta"])

    def test_find_cusips_for_ticker(self):
        """
        Returns all CUSIP records matching a given ticker symbol.
        """
        res = find_cusips_for_ticker("TICKA")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["CUSIP"], "123")

    def test_update_ticker(self):
        """
        Propagates a ticker rename across stocks.csv, all quarterly CSVs, and non_quarterly.csv.
        """
        update_ticker("TICKA", "TICKNEW")

        df_stocks = load_stocks()
        self.assertEqual(df_stocks.loc["123", "Ticker"], "TICKNEW")

        df_q = load_fund_holdings("Fund A", "2025Q1")
        self.assertEqual(df_q.iloc[0]["Ticker"], "TICKNEW")

        df_nq = load_non_quarterly_data()
        self.assertEqual(df_nq.iloc[0]["Ticker"], "TICKNEW")

    def test_update_ticker_with_new_company_name(self):
        """
        Propagates a ticker rename with a new company name across stocks.csv.
        """
        update_ticker("TICKA", "TICKNEW", new_company="New Company Name")

        df_stocks = load_stocks()
        self.assertEqual(df_stocks.loc["123", "Ticker"], "TICKNEW")
        self.assertEqual(df_stocks.loc["123", "Company"], "New Company Name")

    def test_update_ticker_without_company_preserves_existing(self):
        """
        When no new company name is given, the existing company name is preserved.
        """
        update_ticker("TICKA", "TICKNEW")

        df_stocks = load_stocks()
        self.assertEqual(df_stocks.loc["123", "Ticker"], "TICKNEW")
        self.assertEqual(df_stocks.loc["123", "Company"], "Company A")

    def test_concurrent_save_stocks(self):
        """
        All records written by concurrent threads must be durably saved with no data loss.

        Uses a moderate concurrency footprint (5 threads x 10 iterations) to
        exercise the file-based lock without making the test timing-sensitive.
        Captures stdout so that silent failures swallowed by save_stock's
        broad except surface as test failures instead of hiding behind a
        misleading record-count assertion.
        """
        num_threads = 5
        iterations = 10
        stocks_path = str(Path(self.test_db_folder) / STOCKS_FILE)

        barrier = threading.Barrier(num_threads)
        errors = []
        captured_stdout = io.StringIO()
        stdout_lock = threading.Lock()

        class _ThreadSafeWriter:
            def write(self, data):
                with stdout_lock:
                    captured_stdout.write(data)

            def flush(self):
                pass

        def worker(thread_idx):
            try:
                barrier.wait()
                for i in range(iterations):
                    save_stock(
                        f"C_{thread_idx}_{i}", f"T_{thread_idx}_{i}", f"Company_{thread_idx}_{i}"
                    )
            except Exception as e:
                errors.append(f"Thread {thread_idx}: {str(e)}")

        with unittest.mock.patch("sys.stdout", _ThreadSafeWriter()):
            threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        self.assertEqual(len(errors), 0, f"Thread-level errors: {errors}")
        stdout_text = captured_stdout.getvalue()
        self.assertNotIn(
            "An error occurred while writing",
            stdout_text,
            f"save_stock reported silent failures:\n{stdout_text}",
        )

        df = load_stocks(stocks_path)
        expected_new_records = num_threads * iterations
        self.assertEqual(len(df), 2 + expected_new_records)

        for t_idx in range(num_threads):
            for i in range(iterations):
                cusip = f"C_{t_idx}_{i}"
                ticker = f"T_{t_idx}_{i}"
                self.assertIn(cusip, df.index, f"Missing CUSIP: {cusip}")
                self.assertEqual(df.loc[cusip, "Ticker"], ticker)

    def test_concurrent_save_and_sort(self):
        """
        Concurrent saves and sorts must not corrupt the CSV or raise unhandled exceptions.
        Uses a 1-second window: long enough to exercise real contention, short enough for CI.
        """
        # Saver sleeps 10ms between writes; sorter sleeps 20ms between sorts.
        # In 1 second this exercises ~100 writes and ~50 sorts with real lock contention.
        SAVER_INTERVAL_S = 0.01
        SORTER_INTERVAL_S = 0.02
        RUN_DURATION_S = 1

        stocks_path = str(Path(self.test_db_folder) / STOCKS_FILE)
        stop_event = threading.Event()

        def saver():
            i = 0
            while not stop_event.is_set():
                save_stock(f"S_{i}", f"T_{i}", "Co")
                i += 1
                time.sleep(SAVER_INTERVAL_S)

        def sorter():
            while not stop_event.is_set():
                with contextlib.suppress(Exception):
                    sort_stocks(stocks_path)
                time.sleep(SORTER_INTERVAL_S)

        t1 = threading.Thread(target=saver)
        t2 = threading.Thread(target=sorter)
        t1.start()
        t2.start()

        time.sleep(RUN_DURATION_S)
        stop_event.set()
        t1.join()
        t2.join()

        df = load_stocks(stocks_path)
        self.assertGreater(len(df), 0)

    def test_delete_fund_from_database(self):
        """
        Moves the fund to excluded_hedge_funds.csv carrying its URL from hedge_funds.csv.
        """
        fund_info = {"Fund": "Fund B", "CIK": "002", "URL": "https://fund-b.example.com/"}
        # Create Fund B in hedge_funds.csv first (with URL column)
        with (Path(self.test_db_folder) / HEDGE_FUNDS_FILE).open("a", newline="") as f:
            f.write("002,Fund B,Manager B,Denom B,,https://fund-b.example.com/\n")

        delete_fund_from_database(fund_info)

        # Check file deleted
        self.assertFalse((Path(self.test_db_folder) / "2025Q1" / "Fund_B.csv").exists())

        # Check removed from hedge_funds.csv
        funds = load_hedge_funds()
        self.assertTrue(all(f["Fund"] != "Fund B" for f in funds))

        # Check added to excluded_hedge_funds.csv with URL preserved from hedge_funds.csv
        excluded_path = Path(self.test_db_folder) / "excluded_hedge_funds.csv"
        self.assertTrue(excluded_path.exists())
        df_ex = pd.read_csv(excluded_path)
        self.assertIn("Fund B", df_ex["Fund"].values)
        self.assertIn("https://fund-b.example.com/", df_ex["URL"].values)

    def test_restore_fund_to_database(self):
        """
        Moves a fund record from excluded_hedge_funds.csv back to hedge_funds.csv,
        producing a result sorted alphabetically by Fund (case-insensitive).
        """
        with (Path(self.test_db_folder) / HEDGE_FUNDS_FILE).open("w", newline="") as f:
            f.write("CIK,Fund,Manager,Denomination,CIKs,URL\n")
            f.write('"010","Charlie","Manager C","Denom C","",""\n')
            f.write('"011","apple","Manager A","Denom A","",""\n')
            f.write('"012","delta","Manager D","Denom D","",""\n')

        excluded_path = Path(self.test_db_folder) / "excluded_hedge_funds.csv"
        with excluded_path.open("w", newline="") as f:
            f.write("CIK,Fund,Manager,Denomination,CIKs,URL\n")
            f.write('"099","Bravo","Manager B","Denom B","","https://bravo.example.com/"\n')
            f.write('"100","Other","Manager O","Denom O","",""\n')

        restore_fund_to_database({"Fund": "Bravo", "CIK": "099"})

        # Removed from excluded
        df_ex = pd.read_csv(excluded_path, dtype=str)
        self.assertNotIn("Bravo", df_ex["Fund"].values)
        self.assertIn("Other", df_ex["Fund"].values)

        df_hf = pd.read_csv(Path(self.test_db_folder) / HEDGE_FUNDS_FILE, dtype=str)
        self.assertEqual(list(df_hf["Fund"]), ["apple", "Bravo", "Charlie", "delta"])
        self.assertEqual(
            df_hf.loc[df_hf["Fund"] == "Bravo", "URL"].iloc[0], "https://bravo.example.com/"
        )

    def test_load_excluded_hedge_funds(self):
        """
        Loads excluded hedge funds from CSV as a list of dicts.
        """
        excluded_path = Path(self.test_db_folder) / "excluded_hedge_funds.csv"
        with excluded_path.open("w", newline="") as f:
            f.write("CIK,Fund,Manager,Denomination,CIKs,URL\n")
            f.write('"099","Fund X","Manager X","Denom X","","https://fund-x.example.com/"\n')

        excluded = load_excluded_hedge_funds()
        self.assertEqual(len(excluded), 1)
        self.assertEqual(excluded[0]["Fund"], "Fund X")

    def tearDown(self):
        """
        Clean up the temporary database directory.
        """
        shutil.rmtree(self.test_db_folder, ignore_errors=True)
        self.patcher.stop()


if __name__ == "__main__":
    unittest.main()

import os
import stat
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import app.database as _db
from app.database import update_ticker, update_ticker_for_cusip
from app.database.stocks import (
    load_stocks,
    update_non_quarterly_filings,
    update_quarterly_filings,
)

_STOCKS_CSV = (
    "CUSIP,Ticker,Company,Industry\n"
    '"C1","OLD","Old Corp","Tech"\n'
    '"C2","OLD","Old Corp","Tech"\n'
    '"C3","KEEP","Keep Inc","Health"\n'
)
_QUARTER_CSV = (
    "CUSIP,Ticker,Company,Shares,Delta_Shares,Value,Delta_Value,Delta,Portfolio%\n"
    "C1,OLD,Old Corp,1000,0,1M,0,NO CHANGE,10%\n"
    "C3,KEEP,Keep Inc,500,0,500K,0,NO CHANGE,5%\n"
)
_NQ_CSV = (
    "Fund,CUSIP,Ticker,Company,Shares,Value,Avg_Price,Date,Filing_Date\n"
    "FundA,C2,OLD,Old Corp,200,100K,500,2026-01-01,2026-01-03\n"
)


class TestTickerCascade(unittest.TestCase):
    def setUp(self):
        """
        Build a temp database (stocks + one quarter + non-quarterly) and point
        DB_FOLDER at it.
        """
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        (root / "stocks.csv").write_text(_STOCKS_CSV, encoding="utf-8")
        (root / "non_quarterly.csv").write_text(_NQ_CSV, encoding="utf-8")
        quarter = root / "2025Q1"
        quarter.mkdir()
        (quarter / "FundA.csv").write_text(_QUARTER_CSV, encoding="utf-8")

        patcher = patch.object(_db, "DB_FOLDER", str(root))
        patcher.start()
        self.addCleanup(patcher.stop)
        load_stocks.cache_clear()
        self.addCleanup(load_stocks.cache_clear)
        self.root = root

    def _stocks_rows(self):
        """Return stocks.csv as a list of (cusip, ticker) tuples."""
        df = load_stocks().reset_index()
        return list(zip(df["CUSIP"], df["Ticker"]))

    def test_update_ticker_cascades_to_all_files(self):
        """
        Renaming a ticker rewrites every matching CUSIP in stocks.csv, the
        quarterly filing and non_quarterly.csv, leaving other tickers intact.
        """
        update_ticker("OLD", "NEW", new_company="New Corp")

        self.assertCountEqual(self._stocks_rows(), [("C1", "NEW"), ("C2", "NEW"), ("C3", "KEEP")])
        quarter_text = (self.root / "2025Q1" / "FundA.csv").read_text(encoding="utf-8")
        self.assertIn("C1,NEW,", quarter_text)
        self.assertIn("C3,KEEP,", quarter_text)
        nq_text = (self.root / "non_quarterly.csv").read_text(encoding="utf-8")
        self.assertIn('"C2","NEW"', nq_text)

    def _stocks_industries(self):
        """Return stocks.csv as a list of (cusip, industry) tuples."""
        df = load_stocks().reset_index()
        return list(zip(df["CUSIP"], df["Industry"]))

    def test_update_ticker_rewrites_the_industry_when_given_one(self):
        """
        A rename that comes with a new industry replaces it on every matching
        CUSIP, since a reverse merger leaves the stored one describing the old
        business.
        """
        update_ticker("OLD", "NEW", new_company="New Corp", new_industry="Aerospace & Defense")

        self.assertCountEqual(
            self._stocks_industries(),
            [("C1", "Aerospace & Defense"), ("C2", "Aerospace & Defense"), ("C3", "Health")],
        )

    def test_update_ticker_keeps_the_industry_when_not_given_one(self):
        """
        An unresolvable industry must not blank the stored one.
        """
        update_ticker("OLD", "NEW", new_company="New Corp")

        self.assertCountEqual(
            self._stocks_industries(), [("C1", "Tech"), ("C2", "Tech"), ("C3", "Health")]
        )

    def test_update_ticker_for_cusip_only_touches_that_cusip(self):
        """
        A single-CUSIP rename leaves the ticker's other CUSIPs untouched.
        """
        update_ticker_for_cusip("C1", "SOLO")

        self.assertCountEqual(self._stocks_rows(), [("C1", "SOLO"), ("C2", "OLD"), ("C3", "KEEP")])
        quarter_text = (self.root / "2025Q1" / "FundA.csv").read_text(encoding="utf-8")
        self.assertIn("C1,SOLO,", quarter_text)

    def _stocks_companies(self):
        """
        Return stocks.csv as a list of (cusip, company) tuples.
        """
        df = load_stocks().reset_index()
        return list(zip(df["CUSIP"], df["Company"], strict=True))

    def test_update_ticker_normalizes_the_new_company_name(self):
        """
        A provider-padded company name is normalized like every other stocks.csv writer.
        """
        update_ticker("OLD", "NEW", new_company="New Corp, Inc. Common Stock")

        self.assertCountEqual(
            self._stocks_companies(),
            [("C1", "New Corp Inc"), ("C2", "New Corp Inc"), ("C3", "Keep Inc")],
        )

    def test_update_ticker_for_cusip_normalizes_the_new_company_name(self):
        """
        The single-CUSIP rename normalizes the new company name too.
        """
        update_ticker_for_cusip("C1", "SOLO", new_company="Solo Holdings, Inc. Ordinary Shares")

        self.assertIn(("C1", "Solo Holdings Inc"), self._stocks_companies())

    def test_update_ticker_keeps_the_stocks_file_mode(self):
        """
        The rewrite goes through the shared atomic writer, which restores the target's mode.
        """
        mode = stat.S_IMODE((self.root / "stocks.csv").stat().st_mode)

        with patch("app.utils.pd.Path.chmod") as chmod:
            update_ticker("OLD", "NEW")

        self.assertIn(mode, [call.args[0] for call in chmod.call_args_list])

    @unittest.skipIf(os.name == "nt", "POSIX permission bits")
    def test_update_ticker_does_not_narrow_a_0644_stocks_file(self):
        """
        mkstemp creates 0600 temp files; the swapped-in stocks.csv must stay 0644.
        """
        stocks_path = self.root / "stocks.csv"
        stocks_path.chmod(0o644)

        update_ticker("OLD", "NEW")

        self.assertEqual(stat.S_IMODE(stocks_path.stat().st_mode), 0o644)

    def _assert_waits_for_lock(self, target, lock_path, run):
        """
        Runs ``run`` in a thread while ``lock_path`` is held and checks that
        ``target`` is only rewritten once the lock is released.
        """
        original = target.read_text(encoding="utf-8")
        lock_path.touch()
        worker = threading.Thread(target=run)
        worker.start()
        try:
            time.sleep(0.4)
            self.assertEqual(target.read_text(encoding="utf-8"), original)
        finally:
            lock_path.unlink()
            worker.join(timeout=10)
        self.assertFalse(worker.is_alive())
        self.assertNotEqual(target.read_text(encoding="utf-8"), original)

    def test_non_quarterly_update_waits_for_the_file_lock(self):
        """
        A concurrent holder of the non_quarterly.csv lock blocks the ticker rewrite.
        """
        self._assert_waits_for_lock(
            self.root / "non_quarterly.csv",
            self.root / "non_quarterly.csv.lock",
            lambda: update_non_quarterly_filings(["C2"], "NEW"),
        )

    def test_quarterly_update_waits_for_the_file_lock(self):
        """
        A concurrent holder of a quarter file's lock blocks the ticker rewrite.
        """
        quarter_file = self.root / "2025Q1" / "FundA.csv"
        self._assert_waits_for_lock(
            quarter_file,
            quarter_file.with_name("FundA.csv.lock"),
            lambda: update_quarterly_filings(["C1"], "NEW"),
        )

    def test_update_unknown_ticker_is_a_noop(self):
        """
        Renaming a ticker that doesn't exist changes nothing.
        """
        update_ticker("GHOST", "NEW")

        self.assertCountEqual(self._stocks_rows(), [("C1", "OLD"), ("C2", "OLD"), ("C3", "KEEP")])


if __name__ == "__main__":
    unittest.main()

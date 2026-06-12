import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app.database as _db
from app.database import update_ticker, update_ticker_for_cusip
from app.database.stocks import load_stocks

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

    def test_update_ticker_for_cusip_only_touches_that_cusip(self):
        """
        A single-CUSIP rename leaves the ticker's other CUSIPs untouched.
        """
        update_ticker_for_cusip("C1", "SOLO")

        self.assertCountEqual(self._stocks_rows(), [("C1", "SOLO"), ("C2", "OLD"), ("C3", "KEEP")])
        quarter_text = (self.root / "2025Q1" / "FundA.csv").read_text(encoding="utf-8")
        self.assertIn("C1,SOLO,", quarter_text)

    def test_update_unknown_ticker_is_a_noop(self):
        """
        Renaming a ticker that doesn't exist changes nothing.
        """
        update_ticker("GHOST", "NEW")

        self.assertCountEqual(self._stocks_rows(), [("C1", "OLD"), ("C2", "OLD"), ("C3", "KEEP")])


if __name__ == "__main__":
    unittest.main()

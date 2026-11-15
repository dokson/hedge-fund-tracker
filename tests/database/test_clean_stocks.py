import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app.database as _db
from app.database.stocks import clean_stocks, load_stocks

_STOCKS_CSV = (
    "CUSIP,Ticker,Company,Industry\n"
    '"00183L201","ANGI","Angi Inc","Internet Content & Information"\n'
    '"00183L102","ANGI","Angi Inc","Internet Content & Information"\n'
    '"00183LAA9","ANGI","Angi Inc","Internet Content & Information"\n'
)
_QUARTER_CSV = (
    "CUSIP,Ticker,Company,Shares,Delta_Shares,Value,Delta_Value,Delta,Portfolio%\n"
    "00183L201,ANGI,ANGI INC,323720,0,4.99M,0,NO CHANGE,1%\n"
)
_NQ_CSV = "Fund,CUSIP,Ticker,Company,Shares,Value,Avg_Price,Date,Filing_Date\n"


class TestCleanStocks(unittest.TestCase):
    def setUp(self):
        """
        Build a temp database where a ticker has its held CUSIP, a retired
        equity CUSIP and a debt CUSIP, the last two in no saved filing.
        """
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        (root / "stocks.csv").write_text(_STOCKS_CSV, encoding="utf-8")
        (root / "non_quarterly.csv").write_text(_NQ_CSV, encoding="utf-8")
        (root / "2025Q1").mkdir()
        (root / "2025Q1" / "FundA.csv").write_text(_QUARTER_CSV, encoding="utf-8")

        patcher = patch.object(_db, "DB_FOLDER", str(root))
        patcher.start()
        self.addCleanup(patcher.stop)
        load_stocks.cache_clear()
        self.addCleanup(load_stocks.cache_clear)

    def test_retired_equity_cusip_survives_debt_orphan_goes(self):
        """
        A retired equity CUSIP (pre-reverse-split) only lives in the filing
        before the oldest saved quarter: the providers can no longer resolve it,
        and without its stocks.csv row a regenerate cannot link the CUSIP change
        and writes a CLOSE row with no ticker. Debt orphans are never linked.
        """
        clean_stocks()

        load_stocks.cache_clear()
        self.assertCountEqual(load_stocks().index, ["00183L201", "00183L102"])


if __name__ == "__main__":
    unittest.main()

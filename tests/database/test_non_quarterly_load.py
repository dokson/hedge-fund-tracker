import tempfile
import unittest
from pathlib import Path

import pandas as pd

from app.database import load_non_quarterly_data

HEADER = '"Fund","CUSIP","Ticker","Company","Shares","Value","Avg_Price","Date","Filing_Date"\n'


class TestLoadNonQuarterlyData(unittest.TestCase):
    def setUp(self):
        """
        Creates a temporary directory for the non-quarterly CSV.
        """
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "non_quarterly.csv")

    def tearDown(self):
        """
        Removes the temporary directory.
        """
        self.tmp.cleanup()

    def _write(self, *rows):
        """
        Writes the given CSV rows under the non-quarterly header.
        """
        with Path(self.path).open("w", encoding="utf-8", newline="\n") as f:
            f.write(HEADER + "".join(row + "\n" for row in rows))

    def test_unresolved_tickers_with_distinct_cusips_are_all_kept(self):
        """
        Rows without a ticker are told apart by CUSIP instead of collapsing on the empty ticker.
        """
        self._write(
            '"Fund A","CUSIP0001","","One Co","10","","","2026-06-02","2026-06-03"',
            '"Fund A","CUSIP0002","","Two Co","20","","","2026-06-01","2026-06-02"',
        )

        df = load_non_quarterly_data(self.path)

        self.assertEqual(sorted(df["CUSIP"]), ["CUSIP0001", "CUSIP0002"])

    def test_same_ticker_keeps_only_the_latest_row(self):
        """
        Resolved rows still keep only the most recent entry per fund and ticker.
        """
        self._write(
            '"Fund A","CUSIP0001","TICK","One Co","10","","","2026-06-01","2026-06-02"',
            '"Fund A","CUSIP0009","TICK","One Co","15","","","2026-06-05","2026-06-06"',
            '"Fund B","CUSIP0001","TICK","One Co","30","","","2026-06-01","2026-06-02"',
        )

        df = load_non_quarterly_data(self.path)

        self.assertEqual(len(df), 2)
        self.assertEqual(int(df[df["Fund"] == "Fund A"].iloc[0]["Shares"]), 15)

    def test_latest_only_false_returns_every_row(self):
        """
        The raw view keeps superseded rows, so the file can be rewritten without losing them.
        """
        self._write(
            '"Fund A","CUSIP0001","TICK","One Co","10","","","2026-06-01","2026-06-02"',
            '"Fund A","CUSIP0001","TICK","One Co","15","","","2026-06-05","2026-06-06"',
        )

        self.assertEqual(len(load_non_quarterly_data(self.path, latest_only=False)), 2)


class TestNqPositionKey(unittest.TestCase):
    def test_key_prefers_ticker_then_cusip_then_row(self):
        """
        A resolved ticker identifies the position; otherwise the CUSIP does; a row with
        neither is unique to itself.
        """
        from app.database import nq_position_key

        df = pd.DataFrame(
            {
                "Ticker": ["TICK", None, "", float("nan"), ""],
                "CUSIP": ["CUSIP0001", "CUSIP0002", "CUSIP0003", None, ""],
            }
        )

        keys = nq_position_key(df)

        self.assertEqual(len(set(keys)), 5)
        self.assertNotEqual(keys.iloc[1], keys.iloc[2])
        self.assertNotEqual(keys.iloc[3], keys.iloc[4])


if __name__ == "__main__":
    unittest.main()

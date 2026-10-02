"""
nq_position_key and the non-quarterly loader, pinned to the fixture shared
with the TypeScript de-duplication.
"""

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from app.database import load_non_quarterly_data, nq_position_key

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "nq_position_keys.json"


class TestNqPositionKeyParity(unittest.TestCase):
    """
    Pins nq_position_key to the fixture shared with the TypeScript de-duplication.
    """

    def setUp(self):
        """
        Loads the shared fixture into a DataFrame shaped like non_quarterly.csv.
        """
        self.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.df = pd.DataFrame(self.fixture["rows"])

    def test_keys_match_fixture(self):
        """
        Each row's position key equals the fixture's expected key.
        """
        self.assertEqual(nq_position_key(self.df).tolist(), self.fixture["keys"])

    def test_loader_keeps_the_latest_row_per_fund_and_key(self):
        """
        load_non_quarterly_data keeps exactly the fixture's surviving rows.
        """
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "non_quarterly.csv"
            self.df.assign(Row=self.df.index).to_csv(path, index=False)
            kept = load_non_quarterly_data(str(path))
        self.assertEqual(sorted(kept["Row"].tolist()), self.fixture["surviving"])

    def test_loader_breaks_date_ties_by_file_order(self):
        """
        Two rows of one position with identical dates resolve to the first in the file, every time.
        """
        tie = pd.DataFrame(
            {
                "Fund": ["F"] * 2,
                "Ticker": ["TT"] * 2,
                "CUSIP": ["000000009"] * 2,
                "Date": ["2026-07-01"] * 2,
                "Filing_Date": ["2026-07-02"] * 2,
                "Row": [0, 1],
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "non_quarterly.csv"
            tie.to_csv(path, index=False)
            kept = load_non_quarterly_data(str(path))
        self.assertEqual(kept["Row"].tolist(), [0])


if __name__ == "__main__":
    unittest.main()

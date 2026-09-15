import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.database import SPLITS_FILE
from app.database.splits import load_split_factors, save_split_factors


class TestSplitsRegistry(unittest.TestCase):
    def test_loads_factors_grouped_by_quarter(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, SPLITS_FILE).write_text(
                "Quarter,CUSIP,Ticker,Factor\n"
                "2025Q4,64110L106,NFLX,10.0\n"
                "2025Q4,81762P102,NOW,5.0\n"
                "2026Q2,146869102,CVNA,5.0\n",
                encoding="utf-8",
            )

            with patch("app.database.DB_FOLDER", folder):
                factors = load_split_factors()

        self.assertEqual(
            factors,
            {
                "2025Q4": {"64110L106": 10.0, "81762P102": 5.0},
                "2026Q2": {"146869102": 5.0},
            },
        )

    def test_returns_empty_when_the_registry_is_absent(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch("app.database.DB_FOLDER", folder):
                self.assertEqual(load_split_factors(), {})

    def test_saved_registry_round_trips(self):
        rows = [
            {
                "Quarter": "2026Q2",
                "Date": "2026-05-08",
                "CUSIP": "146869102",
                "Ticker": "CVNA",
                "Factor": 5.0,
            },
            {
                "Quarter": "2025Q4",
                "Date": "2025-11-17",
                "CUSIP": "64110L106",
                "Ticker": "NFLX",
                "Factor": 10.0,
            },
        ]

        with tempfile.TemporaryDirectory() as folder:
            with patch("app.database.DB_FOLDER", folder):
                save_split_factors(rows)
                self.assertEqual(
                    load_split_factors(),
                    {"2025Q4": {"64110L106": 10.0}, "2026Q2": {"146869102": 5.0}},
                )
                saved = Path(folder, SPLITS_FILE).read_text(encoding="utf-8")

        # Chronological order keeps the committed file's diffs append-only.
        self.assertLess(saved.index("NFLX"), saved.index("CVNA"))
        # The ex-date travels with the factor, and is what tells a provider row
        # from one inferred by holder agreement, which carries none.
        self.assertIn("Quarter,Date,CUSIP,Ticker,Factor", saved)
        self.assertIn("2025-11-17", saved)


class TestIncrementalSave(unittest.TestCase):
    EXISTING = (
        "Quarter,Date,CUSIP,Ticker,Factor\n"
        "2025Q4,2025-11-17,64110L106,NFLX,10.0\n"
        "2026Q1,2026-03-23,861896108,SNEX,1.5\n"
    )

    def test_replacing_one_quarter_leaves_the_others_alone(self):
        fresh = [
            {
                "Quarter": "2026Q1",
                "Date": "2026-02-02",
                "CUSIP": "946760105",
                "Ticker": "CLMB",
                "Factor": 4.0,
            }
        ]

        with tempfile.TemporaryDirectory() as folder:
            Path(folder, SPLITS_FILE).write_text(self.EXISTING, encoding="utf-8")
            with patch("app.database.DB_FOLDER", folder):
                save_split_factors(fresh, replacing=["2026Q1"])
                factors = load_split_factors()

        self.assertEqual(
            factors,
            {"2025Q4": {"64110L106": 10.0}, "2026Q1": {"946760105": 4.0}},
        )

    def test_a_rescanned_quarter_with_no_splits_loses_its_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, SPLITS_FILE).write_text(self.EXISTING, encoding="utf-8")
            with patch("app.database.DB_FOLDER", folder):
                save_split_factors([], replacing=["2026Q1"])
                factors = load_split_factors()

        self.assertEqual(factors, {"2025Q4": {"64110L106": 10.0}})

    def test_saving_without_replacing_rewrites_the_whole_registry(self):
        fresh = [
            {
                "Quarter": "2026Q2",
                "Date": "2026-05-08",
                "CUSIP": "146869102",
                "Ticker": "CVNA",
                "Factor": 5.0,
            }
        ]

        with tempfile.TemporaryDirectory() as folder:
            Path(folder, SPLITS_FILE).write_text(self.EXISTING, encoding="utf-8")
            with patch("app.database.DB_FOLDER", folder):
                save_split_factors(fresh)
                factors = load_split_factors()

        self.assertEqual(factors, {"2026Q2": {"146869102": 5.0}})


if __name__ == "__main__":
    unittest.main()

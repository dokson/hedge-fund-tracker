import csv
import tempfile
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

from app.backtest.report import CSV_FIELDS, rebuild_strategy_performance, write_rows


def _full_analysis(rows: list[dict]) -> pd.DataFrame:
    """
    Build a stock-level frame carrying every column the six strategies rank on.
    """
    cols = {
        "Holder_Count": 0,
        "Avg_Portfolio_Pct": 0.0,
        "Max_Portfolio_Pct": 0.0,
        "Net_Buyers": 0,
        "New_Holder_Count": 0,
        "Delta": 0.0,
        "Total_Delta_Value": 0.0,
    }
    return pd.DataFrame([{**cols, **r} for r in rows])


class TestWriteRows(unittest.TestCase):
    """
    Tests for the atomic long-format CSV writer.
    """

    def setUp(self):
        """
        Create a temp output path.
        """
        self.tmp = tempfile.mkdtemp(prefix="hft_perf_")
        self.path = Path(self.tmp) / "performance.csv"

    def tearDown(self):
        """
        Remove the temp directory.
        """
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_writes_header_and_rows(self):
        """
        The CSV is written with the canonical header and one row per input dict.
        """
        rows = [
            dict.fromkeys(CSV_FIELDS) | {"series_type": "strategy", "series_id": "avg_portfolio"}
        ]
        write_rows(rows, self.path)
        with self.path.open(newline="", encoding="utf-8") as handle:
            reader = list(csv.DictReader(handle))
        self.assertEqual(list(reader[0].keys()), CSV_FIELDS)
        self.assertEqual(reader[0]["series_id"], "avg_portfolio")

    def test_empty_rows_still_writes_header(self):
        """
        With no windows, an empty CSV (header only) is still produced.
        """
        write_rows([], self.path)
        with self.path.open(newline="", encoding="utf-8") as handle:
            content = handle.read()
        self.assertIn("series_id", content)


class TestRebuild(unittest.TestCase):
    """
    End-to-end rebuild with injected dependencies (no DB / network).
    """

    def setUp(self):
        """
        Temp output path.
        """
        self.tmp = tempfile.mkdtemp(prefix="hft_perf_")
        self.path = Path(self.tmp) / "performance.csv"

    def tearDown(self):
        """
        Remove the temp directory.
        """
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_rebuild_writes_strategy_and_benchmark_rows(self):
        """
        Rebuild runs all strategies + benchmarks and persists the long CSV.
        """
        analysis = {
            "2025Q1": _full_analysis(
                [
                    {
                        "Ticker": "AAA",
                        "Holder_Count": 20,
                        "Avg_Portfolio_Pct": 10.0,
                        "Max_Portfolio_Pct": 40.0,
                        "Net_Buyers": 8,
                        "New_Holder_Count": 2,
                        "Delta": 30.0,
                    },
                    {
                        "Ticker": "BBB",
                        "Holder_Count": 16,
                        "Avg_Portfolio_Pct": 5.0,
                        "Max_Portfolio_Pct": 20.0,
                        "Net_Buyers": 5,
                        "New_Holder_Count": 1,
                        "Delta": 10.0,
                    },
                ]
            )
        }
        prices = {
            ("AAA", "2025-05-15"): 100.0,
            ("AAA", "2025-08-14"): 120.0,
            ("BBB", "2025-05-15"): 50.0,
            ("BBB", "2025-08-14"): 55.0,
            ("SPY", "2025-05-15"): 400.0,
            ("SPY", "2025-08-14"): 420.0,
            ("QQQ", "2025-05-15"): 300.0,
            ("QQQ", "2025-08-14"): 330.0,
        }

        rebuild_strategy_performance(
            path=self.path,
            price_fn=lambda t, d: prices.get((t, d.isoformat())),
            as_of=date(2025, 9, 1),
            analysis_fn=lambda q: analysis[q],
            quarters=["2025Q1", "2025Q2"],
            fund_count_fn=lambda _q: 150,  # threshold 15
        )

        with self.path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        series = {(r["series_type"], r["series_id"]) for r in rows}
        self.assertIn(("benchmark", "SPY"), series)
        self.assertIn(("strategy", "avg_portfolio"), series)
        # avg_portfolio holds AAA+BBB -> conviction-weighted +16.667%
        avg = next(r for r in rows if r["series_id"] == "avg_portfolio")
        self.assertAlmostEqual(float(avg["window_return"]), 0.16667, places=4)


if __name__ == "__main__":
    unittest.main()

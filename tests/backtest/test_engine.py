import unittest
from datetime import date

import pandas as pd

from app.backtest.engine import (
    Benchmark,
    build_screen,
    min_holders_for_quarter,
    quarter_entry_date,
    run_backtest,
)
from app.backtest.strategies import strategy_by_id


def _analysis(rows: list[dict]) -> pd.DataFrame:
    """
    Build a stock-level analysis frame with the columns strategies rank on.
    """
    return pd.DataFrame(rows)


ANALYSIS = {
    "2025Q1": _analysis(
        [
            {
                "Ticker": "AAA",
                "Holder_Count": 20,
                "Avg_Portfolio_Pct": 10.0,
                "Max_Portfolio_Pct": 40.0,
            },
            {
                "Ticker": "BBB",
                "Holder_Count": 16,
                "Avg_Portfolio_Pct": 5.0,
                "Max_Portfolio_Pct": 60.0,
            },
            {
                "Ticker": "CCC",
                "Holder_Count": 10,
                "Avg_Portfolio_Pct": 8.0,
                "Max_Portfolio_Pct": 90.0,
            },
        ]
    ),
    "2025Q2": _analysis(
        [
            {
                "Ticker": "AAA",
                "Holder_Count": 18,
                "Avg_Portfolio_Pct": 6.0,
                "Max_Portfolio_Pct": 30.0,
            },
            {
                "Ticker": "DDD",
                "Holder_Count": 15,
                "Avg_Portfolio_Pct": 6.0,
                "Max_Portfolio_Pct": 20.0,
            },
        ]
    ),
}

PRICES = {
    ("AAA", "2025-05-15"): 100.0,
    ("BBB", "2025-05-15"): 50.0,
    ("SPY", "2025-05-15"): 400.0,
    ("QQQ", "2025-05-15"): 300.0,
    ("AAA", "2025-08-14"): 120.0,  # +20%
    ("BBB", "2025-08-14"): 55.0,  # +10%
    ("SPY", "2025-08-14"): 420.0,  # +5%
    ("QQQ", "2025-08-14"): 330.0,  # +10%
    ("AAA", "2025-11-14"): 132.0,  # +10% over window 2
    ("DDD", "2025-08-14"): 60.0,
    ("DDD", "2025-11-14"): 66.0,  # +10%
    ("SPY", "2025-11-14"): 441.0,  # +5%
    ("QQQ", "2025-11-14"): 363.0,  # +10%
}

BENCHES = [Benchmark("SPY", "S&P 500"), Benchmark("QQQ", "Nasdaq 100")]


def _price(ticker: str, day: date) -> float | None:
    """
    Deterministic price lookup over the PRICES table.
    """
    return PRICES.get((ticker, day.isoformat()))


def _analysis_fn(quarter: str) -> pd.DataFrame:
    """
    Return the canned analysis frame for a quarter.
    """
    return ANALYSIS[quarter]


def _run(as_of: date, strategy_ids=("avg_portfolio",)):
    """
    Run the backtest over the canned data with a fixed 150-fund universe (threshold 15).
    """
    return run_backtest(
        price_fn=_price,
        as_of=as_of,
        analysis_fn=_analysis_fn,
        quarters=["2025Q1", "2025Q2", "2025Q3"],
        strategies=[strategy_by_id(sid) for sid in strategy_ids],
        benchmarks=BENCHES,
        fund_count_fn=lambda _q: 150,  # -> threshold 15
    )


class TestBuildScreen(unittest.TestCase):
    """
    Tests for per-strategy screen reconstruction + weighting.
    """

    def test_avg_portfolio_weights_normalized(self):
        """
        Avg Portfolio screen filters by holders and weights by Avg_Portfolio_Pct.
        """
        weights = build_screen(
            "2025Q1", strategy_by_id("avg_portfolio"), threshold=15, analysis_fn=_analysis_fn
        )
        self.assertEqual(set(weights), {"AAA", "BBB"})
        self.assertAlmostEqual(weights["AAA"], 10.0 / 15.0)
        self.assertAlmostEqual(weights["BBB"], 5.0 / 15.0)

    def test_big_bets_selects_by_max_pct(self):
        """
        Big Bets (top-N, no min holders) ranks by Max_Portfolio_Pct.
        """
        weights = build_screen(
            "2025Q1", strategy_by_id("big_bets"), threshold=15, analysis_fn=_analysis_fn, top_n=2
        )
        self.assertEqual(set(weights), {"CCC", "BBB"})  # 90, 60


class TestHelpers(unittest.TestCase):
    """
    Tests for the date + threshold helpers.
    """

    def test_entry_is_quarter_end_plus_45(self):
        """
        Entry date is quarter-end plus the filing lag.
        """
        self.assertEqual(quarter_entry_date("2025Q1"), date(2025, 5, 15))

    def test_min_holders_is_ceil_of_ten_percent(self):
        """
        Threshold is ceil(funds/10), matching the QuarterlyTrends UI default.
        """
        self.assertEqual(min_holders_for_quarter("q", fund_count_fn=lambda _q: 125), 13)
        self.assertEqual(min_holders_for_quarter("q", fund_count_fn=lambda _q: 123), 13)
        self.assertEqual(min_holders_for_quarter("q", fund_count_fn=lambda _q: 120), 12)


class TestRunBacktest(unittest.TestCase):
    """
    Tests for the windowed multi-series backtest.
    """

    def test_consolidated_only(self):
        """
        Windows whose exit has not matured are excluded.
        """
        rows = _run(date(2025, 6, 1))
        self.assertEqual(rows, [])

    def test_emits_benchmark_and_strategy_rows(self):
        """
        One matured window emits both benchmark series plus each strategy.
        """
        rows = _run(date(2025, 9, 1))
        kinds = {(r["series_type"], r["series_id"]) for r in rows}
        self.assertIn(("benchmark", "SPY"), kinds)
        self.assertIn(("benchmark", "QQQ"), kinds)
        self.assertIn(("strategy", "avg_portfolio"), kinds)

    def test_strategy_return_and_excess(self):
        """
        Strategy window return is conviction-weighted; excess is vs the anchor (SPY).
        """
        rows = _run(date(2025, 9, 1))
        strat = next(r for r in rows if r["series_type"] == "strategy")
        self.assertAlmostEqual(strat["window_return"], 0.16667, places=4)
        self.assertAlmostEqual(strat["excess_return"], 0.11667, places=4)
        self.assertEqual(strat["n_stocks"], 2)
        spy = next(r for r in rows if r["series_id"] == "SPY")
        self.assertAlmostEqual(spy["window_return"], 0.05, places=4)
        self.assertIsNone(spy["excess_return"])

    def test_cumulative_compounds(self):
        """
        Cumulative returns compound per series across windows.
        """
        rows = _run(date(2026, 1, 1))
        strat_w2 = [r for r in rows if r["series_type"] == "strategy"][-1]
        # window 2: AAA(+10%) only priced (BBB absent in Q2 screen) -> conv2 = 0.10
        self.assertAlmostEqual(strat_w2["window_return"], 0.10, places=4)
        expected = (1 + 0.16667) * (1 + 0.10) - 1
        self.assertAlmostEqual(strat_w2["cum_return"], expected, places=3)

    def test_multi_strategy_distinct_rows(self):
        """
        Each requested strategy produces its own series rows.
        """
        rows = _run(date(2025, 9, 1), strategy_ids=("avg_portfolio", "big_bets"))
        strat_ids = {r["series_id"] for r in rows if r["series_type"] == "strategy"}
        self.assertEqual(strat_ids, {"avg_portfolio", "big_bets"})


if __name__ == "__main__":
    unittest.main()

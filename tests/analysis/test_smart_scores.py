import unittest
from typing import cast

import pandas as pd

from app.analysis.smart_scores import compute_smart_scores, score_core


def _val(df: pd.DataFrame, ticker: str, column: str) -> float:
    """
    A single score cell as a plain float (pandas-stubs types .loc as a wide Scalar union).
    """
    return cast(float, df.loc[ticker, column])


SCORE_COLUMNS = [
    "Ticker",
    "Smart_Score",
    "Breadth_Score",
    "Momentum_Score",
    "Conviction_Score",
]


def make_stock_df() -> pd.DataFrame:
    """
    Minimal stock-level aggregation frame with three tickers of decreasing strength.
    """
    return pd.DataFrame(
        [
            {
                "Ticker": "AAA",
                "Holder_Count": 10,
                "Net_Buyers": 8,
                "Avg_Portfolio_Pct": 5.0,
                "High_Conviction_Count": 2,
            },
            {
                "Ticker": "BBB",
                "Holder_Count": 5,
                "Net_Buyers": 0,
                "Avg_Portfolio_Pct": 2.0,
                "High_Conviction_Count": 1,
            },
            {
                "Ticker": "CCC",
                "Holder_Count": 1,
                "Net_Buyers": -4,
                "Avg_Portfolio_Pct": 0.5,
                "High_Conviction_Count": 0,
            },
        ]
    )


class TestComputeSmartScores(unittest.TestCase):
    def _compute(self, registry_tickers: list[str] | None = None) -> pd.DataFrame:
        return compute_smart_scores(make_stock_df(), registry_tickers=registry_tickers)

    def test_output_schema(self):
        """
        Output declares the full score schema, one row per ticker in the universe.
        """
        df = self._compute()

        self.assertEqual(list(df.columns), SCORE_COLUMNS)
        self.assertEqual(len(df), 3)

    def test_scores_within_bounds_and_ordered(self):
        """
        Composite scores stay in [1, 10] and dominance across every component
        yields a strictly higher composite.
        """
        df = self._compute().set_index("Ticker")

        self.assertTrue(((df["Smart_Score"] >= 1) & (df["Smart_Score"] <= 10)).all())
        self.assertGreater(_val(df, "AAA", "Smart_Score"), _val(df, "BBB", "Smart_Score"))
        self.assertGreater(_val(df, "BBB", "Smart_Score"), _val(df, "CCC", "Smart_Score"))

    def test_registry_tickers_without_holdings_get_the_floor_score(self):
        """
        Every registry ticker gets a score: no institutional presence means the
        explicit floor (1.0, zeroed components), not a missing row — and the
        held universe's percentiles are not diluted by the zero tail.
        """
        with_registry = self._compute(registry_tickers=["AAA", "BBB", "CCC", "ZZZ"])
        without_registry = self._compute().set_index("Ticker")
        df = with_registry.set_index("Ticker")

        self.assertEqual(len(with_registry), 4)
        self.assertEqual(_val(df, "ZZZ", "Smart_Score"), 1.0)
        self.assertEqual(_val(df, "ZZZ", "Breadth_Score"), 0.0)
        self.assertEqual(
            _val(df, "AAA", "Smart_Score"), _val(without_registry, "AAA", "Smart_Score")
        )

    def test_high_conviction_entries_boost_conviction(self):
        """
        High-conviction new positions add a capped bonus to the Conviction
        percentile: a rare positive signal must only lift, never dilute.
        """
        df = self._compute().set_index("Ticker")

        self.assertEqual(_val(df, "AAA", "Conviction_Score"), 100.0)
        self.assertAlmostEqual(_val(df, "BBB", "Conviction_Score"), 76.7, places=1)
        self.assertAlmostEqual(_val(df, "CCC", "Conviction_Score"), 33.3, places=1)


class TestScoreCore(unittest.TestCase):
    def test_matches_the_boost_free_composite(self):
        """
        The point-in-time core (used by the backtest) equals the published
        composite when no boost applies — one formula, two consumers.
        """
        core = score_core(make_stock_df())
        published = compute_smart_scores(make_stock_df())

        self.assertTrue(((core >= 1) & (core <= 10)).all())
        for idx, ticker in enumerate(make_stock_df()["Ticker"]):
            self.assertAlmostEqual(
                round(float(core.iloc[idx]), 1),
                float(published.set_index("Ticker").loc[ticker, "Smart_Score"]),  # type: ignore[arg-type]
                places=1,
            )


if __name__ == "__main__":
    unittest.main()

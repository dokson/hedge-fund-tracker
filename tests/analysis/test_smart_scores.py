import unittest

import pandas as pd

from app.analysis.smart_scores import _components, score_core


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


class TestScoreCore(unittest.TestCase):
    def test_scores_within_bounds_and_ordered(self):
        """
        Composite scores stay in [1, 10] and dominance across every component
        yields a strictly higher composite.
        """
        core = score_core(make_stock_df())

        self.assertTrue(((core >= 1) & (core <= 10)).all())
        self.assertGreater(core.iloc[0], core.iloc[1])
        self.assertGreater(core.iloc[1], core.iloc[2])

    def test_high_conviction_entries_boost_conviction(self):
        """
        High-conviction new positions add a capped bonus to the Conviction
        percentile: a rare positive signal must only lift, never dilute.
        """
        conviction = _components(make_stock_df())["Conviction_Score"]

        self.assertEqual(conviction.iloc[0], 100.0)
        self.assertAlmostEqual(conviction.iloc[1], 76.7, places=1)
        self.assertAlmostEqual(conviction.iloc[2], 33.3, places=1)


if __name__ == "__main__":
    unittest.main()

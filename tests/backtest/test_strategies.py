import unittest

import numpy as np
import pandas as pd

from app.backtest.strategies import STRATEGIES, select_screen, strategy_by_id


def _frame() -> pd.DataFrame:
    """
    Build a small stock-level analysis frame exercising every ranking column.
    """
    return pd.DataFrame(
        [
            # Ticker  Holder Avg%  Max%  NetBuy NewHold Delta   Total_Delta_Value
            ("AAA", 20, 10.0, 40.0, 8, 2, 30.0, 100.0),
            ("BBB", 16, 5.0, 20.0, 12, 9, 5.0, 50.0),
            ("CCC", 10, 8.0, 60.0, 1, 1, np.inf, 200.0),  # all-new -> infinite delta
            ("DDD", 18, 3.0, 15.0, -4, 0, -25.0, -300.0),  # biggest dollar decrease
            ("EEE", 14, 6.0, 25.0, 3, 1, -50.0, -50.0),  # smaller dollar decrease
        ],
        columns=[
            "Ticker",
            "Holder_Count",
            "Avg_Portfolio_Pct",
            "Max_Portfolio_Pct",
            "Net_Buyers",
            "New_Holder_Count",
            "Delta",
            "Total_Delta_Value",
        ],
    )


class TestStrategies(unittest.TestCase):
    """
    Tests for per-strategy screen selection.
    """

    def test_registry_has_six_strategies(self):
        """
        All six /quarterly strategies are registered with stable ids.
        """
        ids = [s.strategy_id for s in STRATEGIES]
        self.assertEqual(
            set(ids),
            {"avg_portfolio", "consensus", "new_consensus", "big_bets", "increasing", "decreasing"},
        )

    def test_consensus_ranks_by_net_buyers_top_n(self):
        """
        Consensus Buys selects the highest Net_Buyers, capped at top_n.
        """
        spec = strategy_by_id("consensus")
        tickers = list(select_screen(_frame(), spec, threshold=1, top_n=2)["Ticker"])
        self.assertEqual(tickers, ["BBB", "AAA"])  # 12, 8

    def test_big_bets_ranks_by_max_portfolio_pct(self):
        """
        Big Bets selects the highest single-fund conviction.
        """
        spec = strategy_by_id("big_bets")
        tickers = list(select_screen(_frame(), spec, threshold=1, top_n=2)["Ticker"])
        self.assertEqual(tickers, ["CCC", "AAA"])  # 60, 40

    def test_increasing_keeps_only_positive_delta_pct(self):
        """
        Increasing ranks by Δ% (descending), excludes all-new (infinite) names,
        applies min-holders, and keeps only positive deltas.
        """
        spec = strategy_by_id("increasing")
        tickers = list(select_screen(_frame(), spec, threshold=15, top_n=10)["Ticker"])
        # holders>=15: AAA(30), BBB(5), DDD(-25); positive only, desc -> [AAA, BBB]
        self.assertEqual(tickers, ["AAA", "BBB"])

    def test_decreasing_ranks_by_negative_dollar_change_no_min_holders(self):
        """
        Decreasing ranks by Total_Delta_Value (dollar reduction), keeps only
        negative changes, biggest reduction first, and applies no min-holders.
        """
        spec = strategy_by_id("decreasing")
        tickers = list(select_screen(_frame(), spec, threshold=15, top_n=10)["Ticker"])
        # negative Δ$: DDD(-300), EEE(-50); ascending -> [DDD, EEE] (holder count irrelevant)
        self.assertEqual(tickers, ["DDD", "EEE"])

    def test_avg_portfolio_uses_min_holders_no_cap(self):
        """
        Avg Portfolio filters by min holders and is not capped at top_n.
        """
        spec = strategy_by_id("avg_portfolio")
        tickers = list(select_screen(_frame(), spec, threshold=15, top_n=30)["Ticker"])
        # holders>=15: AAA(10), BBB(5), DDD(3); sorted by Avg% desc
        self.assertEqual(tickers, ["AAA", "BBB", "DDD"])


if __name__ == "__main__":
    unittest.main()

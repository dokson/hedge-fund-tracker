import unittest

import pandas as pd

from app.backtest.strategies import STRATEGIES, select_screen, strategy_by_id


class TestSmartScoreStrategy(unittest.TestCase):
    def test_smart_score_leads_the_strategy_roster(self):
        """
        The smart-score screen is a first-class strategy: first in the canonical
        list (tab order) and resolvable by id like every other spec.
        """
        self.assertEqual(STRATEGIES[0].strategy_id, "smart_score")
        self.assertEqual(strategy_by_id("smart_score").sort_column, "Smart_Score")

    def test_screen_ranks_by_smart_score_descending(self):
        """
        The screen picks the highest-scoring names first, capped at top_n.
        """
        df = pd.DataFrame(
            {
                "Ticker": ["AAA", "BBB", "CCC"],
                "Smart_Score": [4.0, 9.0, 7.0],
                "Avg_Portfolio_Pct": [1.0, 2.0, 3.0],
                "Holder_Count": [1, 2, 3],
            }
        )

        screen = select_screen(df, strategy_by_id("smart_score"), threshold=0, top_n=2)

        self.assertEqual(screen["Ticker"].tolist(), ["BBB", "CCC"])


if __name__ == "__main__":
    unittest.main()

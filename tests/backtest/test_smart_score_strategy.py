import unittest

import pandas as pd

from app.backtest.strategies import select_screen, strategy_by_id


class TestSmartScoreStrategy(unittest.TestCase):
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

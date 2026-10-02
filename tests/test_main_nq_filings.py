import unittest
from unittest.mock import patch

import pandas as pd
from yfinance.exceptions import YFRateLimitError

from app import main


class TestViewNqFilingsRateLimit(unittest.TestCase):
    """
    The CLI filings view aborts cleanly when Yahoo rate-limits the price lookup.
    """

    def test_rate_limit_is_logged_and_nothing_is_printed(self):
        """
        A rate limit stops the view with an error log instead of a traceback or a gappy table.
        """
        today = main.eastern_today().strftime("%Y-%m-%d")
        nq = pd.DataFrame({"Fund": ["F"], "Ticker": ["AAA"], "Date": [today], "Delta": [1]})
        quarter = pd.DataFrame(
            {"Fund": ["F"], "Ticker": ["AAA"], "Delta_Shares": [5], "Avg_Price": [1.0]}
        )
        with (
            patch.object(main, "load_non_quarterly_data", return_value=nq),
            patch.object(main, "get_all_quarters", return_value=["2099Q1"]),
            patch.object(main, "get_quarter_data", return_value=quarter),
            patch.object(main, "aggregate_quarter_by_fund", side_effect=lambda df: df),
            patch.object(main.YFinance, "get_stocks_info", side_effect=YFRateLimitError()),
            patch.object(main, "print_dataframe") as mock_print,
            self.assertLogs("app.main", level="ERROR") as cm,
        ):
            main.run_view_nq_filings()

        mock_print.assert_not_called()
        self.assertTrue(any("rate limit" in line.lower() for line in cm.output))


class TestAiAnalystRateLimit(unittest.TestCase):
    """
    The CLI AI analyst reports a Yahoo rate limit instead of an unexpected error.
    """

    def test_rate_limit_is_logged_readably(self):
        """
        A rate-limited ranking logs the rate limit and prints nothing.
        """
        model = {"Client": lambda model: object(), "ID": "m", "Description": "Model"}
        with (
            patch.object(main, "select_ai_model", return_value=model),
            patch.object(main, "get_last_quarter", return_value="2099Q1"),
            patch.object(main, "AnalystAgent") as mock_agent,
            patch.object(main, "print_dataframe") as mock_print,
            patch.object(main, "print_centered"),
            self.assertLogs("app.main", level="ERROR") as cm,
        ):
            mock_agent.return_value.generate_scored_list.side_effect = YFRateLimitError()
            main.run_ai_analyst()

        mock_print.assert_not_called()
        self.assertTrue(any("rate limit" in line.lower() for line in cm.output))
        self.assertFalse(any("unexpected" in line.lower() for line in cm.output))


if __name__ == "__main__":
    unittest.main()

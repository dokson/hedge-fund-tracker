import unittest
from unittest.mock import patch

import pandas as pd

from app.analysis.performance_evaluator import PerformanceEvaluator


class TestPerformanceEvaluator(unittest.TestCase):
    @patch("app.analysis.performance_evaluator.load_fund_holdings")
    @patch("app.analysis.performance_evaluator.get_previous_quarter")
    @patch("app.analysis.fund_performance.get_quarter_date")
    def test_calculate_quarterly_performance_success(
        self, mock_get_quarter_date, mock_get_prev_quarter, mock_load_holdings
    ):
        """
        Tests calculation with all data available and no missing prices.
        """
        mock_get_prev_quarter.return_value = "2024Q4"
        mock_get_quarter_date.return_value = "2025-03-31"

        # Previous quarter holdings (start of quarter)
        df_prev = pd.DataFrame(
            [
                {
                    "CUSIP": "C1",
                    "Ticker": "T1",
                    "Company": "Co1",
                    "Shares": 100,
                    "Value": 1000,
                    "Reported_Price": 10.0,
                },
                {
                    "CUSIP": "C2",
                    "Ticker": "T2",
                    "Company": "Co2",
                    "Shares": 200,
                    "Value": 2000,
                    "Reported_Price": 10.0,
                },
            ]
        )

        # Current quarter holdings (end of quarter)
        df_curr = pd.DataFrame(
            [
                {"CUSIP": "C1", "Shares": 100, "Value": 1100, "Reported_Price": 11.0},
                {"CUSIP": "C2", "Shares": 200, "Value": 1800, "Reported_Price": 9.0},
            ]
        )

        def side_effect(fund, quarter):
            if quarter == "2024Q4":
                return df_prev
            if quarter == "2025Q1":
                return df_curr
            return pd.DataFrame()

        mock_load_holdings.side_effect = side_effect

        result = PerformanceEvaluator.calculate_quarterly_performance(
            "Test Fund",
            "2025Q1",
            split_factors_fn=lambda _p, _c: {},
            universe_prices_fn=lambda _q: {},
            market_return_fn=lambda _t, _s, _e: None,
        )

        # Total Value = 3000
        # W1 = 1/3, R1 = 0.1, WR1 = 0.0333
        # W2 = 2/3, R2 = -0.1, WR2 = -0.0666
        # Portfolio Return = -0.0333...
        equal_fields = [("fund", "Test Fund"), ("quarter", "2025Q1")]
        for field, expected in equal_fields:
            with self.subTest(field=field):
                self.assertEqual(result[field], expected)

        almost_fields = [
            ("portfolio_return", -3.333333333333333),
            ("end_value", 2900.0),  # 3000 * (1 - 0.0333...)
        ]
        for field, expected in almost_fields:
            with self.subTest(field=field):
                self.assertAlmostEqual(float(result[field]), expected)

        with self.subTest(field="top_contributors"):
            top_contributors = result["top_contributors"]
            assert isinstance(top_contributors, list)
            self.assertEqual(len(top_contributors), 2)
            self.assertEqual(top_contributors[0]["Ticker"], "T1")

    @patch("app.analysis.performance_evaluator.load_fund_holdings")
    def test_split_does_not_read_as_a_loss(self, mock_load_holdings):
        """
        A 10:1 split between the filings is restated, like the published series.
        """
        before = pd.DataFrame(
            [{"CUSIP": "C1", "Ticker": "T1", "Company": "Co1", "Shares": 10, "Value": 1000}]
        )
        after = pd.DataFrame(
            [{"CUSIP": "C1", "Ticker": "T1", "Company": "Co1", "Shares": 100, "Value": 1100}]
        )
        for frame in (before, after):
            frame["Reported_Price"] = frame["Value"] / frame["Shares"]
        mock_load_holdings.side_effect = lambda _f, q: before if q == "2024Q4" else after

        result = PerformanceEvaluator.calculate_quarterly_performance(
            "Test Fund",
            "2025Q1",
            split_factors_fn=lambda _p, _c: {"C1": 10.0},
            universe_prices_fn=lambda _q: {},
            market_return_fn=lambda _t, _s, _e: None,
        )
        self.assertAlmostEqual(float(result["portfolio_return"]), 10.0)

    @patch("app.analysis.performance_evaluator.load_fund_holdings")
    @patch("app.analysis.performance_evaluator.get_previous_quarter")
    @patch("app.analysis.fund_performance.get_quarter_date")
    def test_calculate_quarterly_performance_closed_position(
        self, mock_get_quarter_date, mock_get_prev_quarter, mock_load_holdings
    ):
        """
        A position closed by quarter end takes its market return over the quarter.
        """
        mock_get_prev_quarter.return_value = "2024Q4"
        mock_get_quarter_date.side_effect = lambda q: (
            "2024-12-31" if q == "2024Q4" else "2025-03-31"
        )

        df_prev = pd.DataFrame(
            [
                {
                    "CUSIP": "C1",
                    "Ticker": "T1",
                    "Company": "Co1",
                    "Shares": 100,
                    "Value": 1000,
                    "Reported_Price": 10.0,
                }
            ]
        )

        # C1 is closed; an unrelated row keeps the quarter from reading as missing.
        df_curr = pd.DataFrame(
            [{"CUSIP": "OTHER", "Shares": 10, "Value": 100, "Reported_Price": 10.0}]
        )

        def side_effect(fund, quarter):
            if quarter == "2024Q4":
                return df_prev
            if quarter == "2025Q1":
                return df_curr
            return pd.DataFrame()

        mock_load_holdings.side_effect = side_effect

        calls: list[tuple[str, str, str]] = []

        def market(ticker, start, end):
            calls.append((ticker, start.isoformat(), end.isoformat()))
            return 0.2

        result = PerformanceEvaluator.calculate_quarterly_performance(
            "Test Fund",
            "2025Q1",
            split_factors_fn=lambda _p, _c: {},
            universe_prices_fn=lambda _q: {},
            market_return_fn=market,
        )

        self.assertAlmostEqual(float(result["portfolio_return"]), 20.0)
        self.assertAlmostEqual(float(result["end_value"]), 1200.0)
        self.assertEqual(calls, [("T1", "2024-12-31", "2025-03-31")])

    @patch("app.analysis.performance_evaluator.load_fund_holdings")
    def test_calculate_quarterly_performance_missing_data(self, mock_load_holdings):
        mock_load_holdings.return_value = pd.DataFrame()
        result = PerformanceEvaluator.calculate_quarterly_performance("Test Fund", "2025Q1")
        self.assertIn("error", result)
        self.assertIn("Missing data", result["error"])


if __name__ == "__main__":
    unittest.main()

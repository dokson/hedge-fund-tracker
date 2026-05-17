import unittest
from unittest.mock import patch

import pandas as pd

from app.analysis.quarterly_report import generate_comparison
from app.utils.strings import format_percentage, format_value


@patch("app.stocks.ticker_resolver.TickerResolver.resolve_ticker")
class TestReport(unittest.TestCase):
    def test_generate_comparison(self, mock_resolve_ticker):
        def resolve_ticker(df):
            ticker_map = {
                "TC123456": "TSLA",
                "TC789012": "GOOGL",
                "TC345678": "AMZN",
                "TC901234": "MSFT",
            }
            df["Ticker"] = df["CUSIP"].map(ticker_map)
            return df

        mock_resolve_ticker.side_effect = resolve_ticker

        # Create mock DataFrames with multiple stocks
        df_recent = pd.DataFrame(
            [
                {
                    "CUSIP": "TC123456",
                    "Company": "Tesla",
                    "Shares": 1000,
                    "Value": 25000,
                },  # TSLA - Increased
                {
                    "CUSIP": "TC789012",
                    "Company": "Google",
                    "Shares": 200,
                    "Value": 5000,
                },  # GOOGL - New
                {
                    "CUSIP": "TC901234",
                    "Company": "Microsoft",
                    "Shares": 400,
                    "Value": 8000,
                },  # MSFT - No change
            ]
        )
        df_previous = pd.DataFrame(
            [
                {"CUSIP": "TC123456", "Company": "Tesla", "Shares": 500, "Value": 10000},
                {
                    "CUSIP": "TC345678",
                    "Company": "Amazon",
                    "Shares": 300,
                    "Value": 6000,
                },  # AMZN - Closed
                {"CUSIP": "TC901234", "Company": "Microsoft", "Shares": 400, "Value": 8000},
            ]
        )

        df_output = generate_comparison(df_recent, df_previous)

        # The function sorts by ['Delta_Value', 'Value'] descending.
        # Expected order: TSLA, GOOGL, MSFT, AMZN, Total
        # Per-stock expected values, one dict per row. The subTest below tags
        # failures with the position label so diagnostic output points at
        # the exact stock that drifted.
        per_stock = [
            {
                "label": "TSLA (increased)",
                "idx": 0,
                "CUSIP": "TC123456",
                "Ticker": "TSLA",
                "Shares": 1000,
                "Delta_Shares": 500,
                "Value": format_value(25000),
                # Delta_Value = (1000 - 500) * (25000 / 1000) = 12500
                "Delta_Value": format_value(12500),
                "Delta": format_percentage(100, True),
                "Portfolio%": format_percentage((25000 / 38000) * 100),
            },
            {
                "label": "GOOGL (new)",
                "idx": 1,
                "CUSIP": "TC789012",
                "Ticker": "GOOGL",
                "Shares": 200,
                "Delta_Shares": 200,
                "Value": format_value(5000),
                "Delta_Value": format_value(5000),
                "Delta": "NEW",
                "Portfolio%": format_percentage((5000 / 38000) * 100),
            },
            {
                "label": "MSFT (no change)",
                "idx": 2,
                "CUSIP": "TC901234",
                "Ticker": "MSFT",
                "Shares": 400,
                "Delta_Shares": 0,
                "Value": format_value(8000),
                "Delta_Value": format_value(0),
                "Delta": "NO CHANGE",
                "Portfolio%": format_percentage((8000 / 38000) * 100),
            },
            {
                "label": "AMZN (closed)",
                "idx": 3,
                "CUSIP": "TC345678",
                "Ticker": "AMZN",
                "Shares": 0,
                "Delta_Shares": -300,
                "Value": format_value(0),
                "Delta_Value": format_value(-6000),
                "Delta": "CLOSE",
                "Portfolio%": format_percentage(0),
            },
        ]
        for stock in per_stock:
            idx = stock["idx"]
            for column in (
                "CUSIP",
                "Ticker",
                "Shares",
                "Delta_Shares",
                "Value",
                "Delta_Value",
                "Delta",
                "Portfolio%",
            ):
                with self.subTest(stock=stock["label"], column=column):
                    self.assertEqual(df_output.loc[idx, column], stock[column])

        # Totals row: total portfolio = 38000, total delta = 12500 + 5000 - 6000 = 11500,
        # previous portfolio = 10000 + 6000 + 8000 = 24000.
        total_idx = len(df_output) - 1
        total_expected = {
            "CUSIP": "Total",
            "Value": format_value(38000),
            "Delta_Value": format_value(11500),
            "Delta": format_percentage((11500 / 24000) * 100, True),
            "Portfolio%": format_percentage(100),
        }
        for column, expected in total_expected.items():
            with self.subTest(stock="Total", column=column):
                self.assertEqual(df_output.loc[total_idx, column], expected)


if __name__ == "__main__":
    unittest.main()

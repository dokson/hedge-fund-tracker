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


@patch("app.stocks.ticker_resolver.TickerResolver.resolve_ticker")
class TestCusipChangeLinking(unittest.TestCase):
    def test_cusip_change_is_linked_not_new_close(self, mock_resolve_ticker):
        """
        A position whose CUSIP changed between quarters (same resolved ticker)
        must be reported as one continuing position with value-based deltas,
        not as a CLOSE plus a NEW.
        """

        def resolve_ticker(df):
            ticker_map = {
                "TC1111108": "ACME",
                "TC2222106": "ACME",
                "TC9012104": "MSFT",
            }
            df["Ticker"] = df["CUSIP"].map(ticker_map)
            return df

        mock_resolve_ticker.side_effect = resolve_ticker

        df_recent = pd.DataFrame(
            [
                # Same issuer as TC1111108, re-identified under a new CUSIP
                # after a 1:10 reverse split; value drifted +10%.
                {"CUSIP": "TC2222106", "Company": "Acme Corp", "Shares": 100, "Value": 11000},
                {"CUSIP": "TC9012104", "Company": "Microsoft", "Shares": 400, "Value": 8000},
            ]
        )
        df_previous = pd.DataFrame(
            [
                {"CUSIP": "TC1111108", "Company": "Acme Corp", "Shares": 1000, "Value": 10000},
                {"CUSIP": "TC9012104", "Company": "Microsoft", "Shares": 400, "Value": 8000},
            ]
        )

        df_output = generate_comparison(df_recent, df_previous)

        # Two stock rows + Total row: the pair must be collapsed, not 3 rows.
        self.assertEqual(len(df_output), 3)
        deltas = list(df_output["Delta"][:2])
        self.assertNotIn("NEW", deltas)
        self.assertNotIn("CLOSE", deltas)

        # Linked row sorts first (Delta_Value 1000 > 0).
        linked = {
            "CUSIP": "TC2222106",
            "Ticker": "ACME",
            "Shares": 100,
            # Value-equivalent share delta: round(1000 / (11000 / 100)) = 9
            "Delta_Shares": 9,
            "Value": format_value(11000),
            "Delta_Value": format_value(1000),
            # Value-based delta: (11000 - 10000) / 10000 = +10%
            "Delta": format_percentage(10, True),
            "Portfolio%": format_percentage((11000 / 19000) * 100),
        }
        for column, expected in linked.items():
            with self.subTest(row="linked", column=column):
                self.assertEqual(df_output.loc[0, column], expected)

        with self.subTest(row="unchanged"):
            self.assertEqual(df_output.loc[1, "Delta"], "NO CHANGE")

        # Totals: portfolio 19000, previous 18000, delta 1000.
        total_idx = len(df_output) - 1
        total_expected = {
            "Value": format_value(19000),
            "Delta_Value": format_value(1000),
            "Delta": format_percentage((1000 / 18000) * 100, True),
        }
        for column, expected in total_expected.items():
            with self.subTest(row="total", column=column):
                self.assertEqual(df_output.loc[total_idx, column], expected)

    def test_ambiguous_ticker_pairs_are_not_linked(self, mock_resolve_ticker):
        """
        When more than one NEW (or CLOSE) candidate resolves to the same
        ticker, the pairing is ambiguous and rows must be left untouched.
        """

        def resolve_ticker(df):
            df["Ticker"] = "DUPL"
            return df

        mock_resolve_ticker.side_effect = resolve_ticker

        df_recent = pd.DataFrame(
            [
                {"CUSIP": "TC1000101", "Company": "Dupl A", "Shares": 50, "Value": 500},
                {"CUSIP": "TC1000209", "Company": "Dupl B", "Shares": 60, "Value": 600},
            ]
        )
        df_previous = pd.DataFrame(
            [
                {"CUSIP": "TC1000308", "Company": "Dupl C", "Shares": 70, "Value": 700},
            ]
        )

        df_output = generate_comparison(df_recent, df_previous)

        self.assertEqual(len(df_output), 4)
        self.assertEqual(sorted(df_output["Delta"][:3]), ["CLOSE", "NEW", "NEW"])

    def test_bond_and_equity_of_same_issuer_are_not_linked(self, mock_resolve_ticker):
        """
        A debt CUSIP (letters in the issue code, positions 7-8) resolving to
        the issuer's equity ticker must not be linked with an equity NEW or
        CLOSE: they are different instruments, not a CUSIP change.
        """

        def resolve_ticker(df):
            df["Ticker"] = "ACME"
            return df

        mock_resolve_ticker.side_effect = resolve_ticker

        # Recent: a convertible note opened; previous: the equity was closed.
        df_recent = pd.DataFrame(
            [{"CUSIP": "TC1111AB3", "Company": "Acme Corp Note", "Shares": 5000, "Value": 4500}]
        )
        df_previous = pd.DataFrame(
            [{"CUSIP": "TC1111108", "Company": "Acme Corp", "Shares": 1000, "Value": 10000}]
        )

        df_output = generate_comparison(df_recent, df_previous)

        self.assertEqual(len(df_output), 3)
        self.assertEqual(sorted(df_output["Delta"][:2]), ["CLOSE", "NEW"])

    def test_no_previous_quarter_does_not_link(self, mock_resolve_ticker):
        """
        With no previous filing every position is NEW and the linking step
        must be a no-op.
        """

        def resolve_ticker(df):
            df["Ticker"] = df["CUSIP"]
            return df

        mock_resolve_ticker.side_effect = resolve_ticker

        df_recent = pd.DataFrame(
            [{"CUSIP": "TC100001", "Company": "Solo Co", "Shares": 50, "Value": 500}]
        )

        df_output = generate_comparison(df_recent, None)

        self.assertEqual(len(df_output), 2)
        self.assertEqual(df_output.loc[0, "Delta"], "NEW")


if __name__ == "__main__":
    unittest.main()

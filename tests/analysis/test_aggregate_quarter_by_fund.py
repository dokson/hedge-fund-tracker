import unittest
from unittest.mock import patch

import pandas as pd

from app.analysis.stocks import aggregate_quarter_by_fund

_STOCKS = pd.DataFrame(
    [
        {"CUSIP": "C1", "Ticker": "AAPL", "Company": "Apple"},
        {"CUSIP": "C2", "Ticker": "AAPL", "Company": "Apple"},
        {"CUSIP": "C3", "Ticker": "MSFT", "Company": "Microsoft"},
        {"CUSIP": "C4", "Ticker": "TSLA", "Company": "Tesla"},
    ]
).set_index("CUSIP")


def _row(fund, cusip, shares, delta_shares, value, delta_value, pct):
    """
    Builds a per-CUSIP quarterly row as consumed by aggregate_quarter_by_fund.
    """
    return {
        "Fund": fund,
        "CUSIP": cusip,
        "Ticker": "IGNORED",  # dropped and re-joined from the stocks master
        "Company": "IGNORED",
        "Shares": shares,
        "Delta_Shares": delta_shares,
        "Value_Num": value,
        "Delta_Value_Num": delta_value,
        "Portfolio_Pct": pct,
    }


@patch("app.analysis.stocks.load_stocks", return_value=_STOCKS)
class TestAggregateQuarterByFund(unittest.TestCase):
    def test_multiple_cusips_same_ticker_are_merged(self, _stocks):
        """
        Two CUSIPs of one ticker within a fund collapse into a single ticker
        row with summed shares, value and portfolio percentage.
        """
        df = pd.DataFrame(
            [
                _row("FundA", "C1", 1000, 100, 50000, 5000, 4.0),
                _row("FundA", "C2", 500, 0, 25000, 0, 2.0),
            ]
        )

        result = aggregate_quarter_by_fund(df)

        self.assertEqual(len(result), 1)
        row = result.iloc[0]
        self.assertEqual(row["Ticker"], "AAPL")
        self.assertEqual(row["Shares"], 1500)
        self.assertEqual(row["Delta_Shares"], 100)
        self.assertEqual(row["Value"], 75000)
        self.assertEqual(row["Portfolio_Pct"], 6.0)

    def test_delta_labels(self, _stocks):
        """
        Delta is NEW for a fresh position, CLOSE when fully sold, NO CHANGE
        when shares are unchanged, and a signed percentage otherwise.
        """
        df = pd.DataFrame(
            [
                _row("FundA", "C1", 1000, 1000, 50000, 50000, 4.0),  # NEW
                _row("FundA", "C3", 0, -800, 0, -40000, 0.0),  # CLOSE
                _row("FundA", "C4", 600, 0, 30000, 0, 3.0),  # NO CHANGE
            ]
        )

        result = aggregate_quarter_by_fund(df).set_index("Ticker")

        self.assertEqual(result.loc["AAPL", "Delta"], "NEW")
        self.assertEqual(result.loc["MSFT", "Delta"], "CLOSE")
        self.assertEqual(result.loc["TSLA", "Delta"], "NO CHANGE")

    def test_fund_concentration_ratio_sums_top_holdings(self, _stocks):
        """
        Fund_Concentration_Ratio is the summed portfolio percentage of a
        fund's top holdings (≤10), identical for every row of that fund.
        """
        df = pd.DataFrame(
            [
                _row("FundA", "C1", 1000, 0, 50000, 0, 30.0),
                _row("FundA", "C3", 500, 0, 25000, 0, 20.0),
            ]
        )

        result = aggregate_quarter_by_fund(df)

        self.assertTrue((result["Fund_Concentration_Ratio"] == 50.0).all())


if __name__ == "__main__":
    unittest.main()

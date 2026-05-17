import unittest

import pandas as pd

from app.analysis.stocks import (
    _aggregate_stock_data,
    _calculate_derived_metrics,
    _calculate_fund_level_flags,
)


class TestKPILogic(unittest.TestCase):
    def setUp(self):
        # Mock fund-level data (as if returned by aggregate_quarter_by_fund)
        self.df_fund = pd.DataFrame(
            [
                # Fund A: TSLA is NEW, Top 10, and > 3% (High Conviction)
                {
                    "Fund": "FundA",
                    "Ticker": "TSLA",
                    "Company": "Tesla",
                    "Shares": 1000,
                    "Delta_Shares": 1000,
                    "Value": 200000,
                    "Delta_Value": 200000,
                    "Portfolio_Pct": 5.0,
                    "Portfolio_Pct_Rank": 1,
                    "Fund_Concentration_Ratio": 40.0,
                    "Shares_Delta_Pct": 0,
                },
                # Fund B: TSLA is NEW but NOT Top 10 and < 3% (Not High Conviction)
                {
                    "Fund": "FundB",
                    "Ticker": "TSLA",
                    "Company": "Tesla",
                    "Shares": 500,
                    "Delta_Shares": 500,
                    "Value": 100000,
                    "Delta_Value": 100000,
                    "Portfolio_Pct": 1.0,
                    "Portfolio_Pct_Rank": 50,
                    "Fund_Concentration_Ratio": 30.0,
                    "Shares_Delta_Pct": 0,
                },
                # Fund C: TSLA is an existing holding, increased by 50% (Ownership Delta)
                {
                    "Fund": "FundC",
                    "Ticker": "TSLA",
                    "Company": "Tesla",
                    "Shares": 1500,
                    "Delta_Shares": 500,
                    "Value": 300000,
                    "Delta_Value": 100000,
                    "Portfolio_Pct": 10.0,
                    "Portfolio_Pct_Rank": 2,
                    "Fund_Concentration_Ratio": 50.0,
                    "Shares_Delta_Pct": 50.0,
                },
                # Fund A: AAPL is existing, no change
                {
                    "Fund": "FundA",
                    "Ticker": "AAPL",
                    "Company": "Apple",
                    "Shares": 5000,
                    "Delta_Shares": 0,
                    "Value": 500000,
                    "Delta_Value": 0,
                    "Portfolio_Pct": 12.0,
                    "Portfolio_Pct_Rank": 2,
                    "Fund_Concentration_Ratio": 40.0,
                    "Shares_Delta_Pct": 0,
                },
            ]
        )

    def test_kpi_calculations(self):
        """
        Tests TSLA's high-conviction flag, aggregation, and derived metrics across funds.
        """
        # 1. Test Flags — TSLA must be high-conviction only in FundA.
        df_flags = _calculate_fund_level_flags(self.df_fund)
        conviction_cases = [
            ("FundA", True),
            ("FundB", False),  # NEW but rank/pct too low
            ("FundC", False),  # existing position, not NEW
        ]
        for fund, expected in conviction_cases:
            with self.subTest(stage="flags", fund=fund):
                row = df_flags[(df_flags["Fund"] == fund) & (df_flags["Ticker"] == "TSLA")].iloc[0]
                self.assertEqual(bool(row["is_high_conviction"]), expected)

        # 2. Test Aggregation — TSLA summary across funds.
        df_agg = _aggregate_stock_data(df_flags)
        tsla_summary = df_agg[df_agg["Ticker"] == "TSLA"].iloc[0]
        agg_expected = {
            "High_Conviction_Count": 1,  # only FundA
            "Avg_Fund_Concentration": 40.0,  # (40 + 30 + 50) / 3
            "Ownership_Delta_Avg": 50.0,  # only FundC's +50% (NEW positions excluded)
        }
        for col, expected in agg_expected.items():
            with self.subTest(stage="aggregation", column=col):
                self.assertEqual(tsla_summary[col], expected)

        # 3. Test Derived Metrics — values + required-column presence.
        df_derived = _calculate_derived_metrics(df_agg)
        tsla_final = df_derived[df_derived["Ticker"] == "TSLA"].iloc[0]
        with self.subTest(stage="derived", column="Portfolio_Concentration_Avg"):
            self.assertEqual(tsla_final["Portfolio_Concentration_Avg"], 40.0)
        for col in ("High_Conviction_Count", "Ownership_Delta_Avg"):
            with self.subTest(stage="derived", column=col):
                self.assertIn(col, tsla_final)


if __name__ == "__main__":
    unittest.main()

from app.analysis.stocks import _calculate_fund_level_flags, _aggregate_stock_data, _calculate_derived_metrics
import pandas as pd
import unittest


class TestKPILogic(unittest.TestCase):

    def setUp(self):
        # Mock fund-level data (as if returned by aggregate_quarter_by_fund)
        self.df_fund = pd.DataFrame([
            # Fund A: TSLA is NEW, Top 10, and > 3% (High Conviction)
            {'Fund': 'FundA', 'Ticker': 'TSLA', 'Company': 'Tesla', 'Shares': 1000, 'Delta_Shares': 1000, 'Value': 200000, 'Delta_Value': 200000, 'Portfolio_Pct': 5.0, 'Portfolio_Pct_Rank': 1, 'Fund_Concentration_Ratio': 40.0, 'Shares_Delta_Pct': 0},
            # Fund B: TSLA is NEW but NOT Top 10 and < 3% (Not High Conviction)
            {'Fund': 'FundB', 'Ticker': 'TSLA', 'Company': 'Tesla', 'Shares': 500, 'Delta_Shares': 500, 'Value': 100000, 'Delta_Value': 100000, 'Portfolio_Pct': 1.0, 'Portfolio_Pct_Rank': 50, 'Fund_Concentration_Ratio': 30.0, 'Shares_Delta_Pct': 0},
            # Fund C: TSLA is an existing holding, increased by 50% (Ownership Delta)
            {'Fund': 'FundC', 'Ticker': 'TSLA', 'Company': 'Tesla', 'Shares': 1500, 'Delta_Shares': 500, 'Value': 300000, 'Delta_Value': 100000, 'Portfolio_Pct': 10.0, 'Portfolio_Pct_Rank': 2, 'Fund_Concentration_Ratio': 50.0, 'Shares_Delta_Pct': 50.0},
            # Fund A: AAPL is existing, no change
            {'Fund': 'FundA', 'Ticker': 'AAPL', 'Company': 'Apple', 'Shares': 5000, 'Delta_Shares': 0, 'Value': 500000, 'Delta_Value': 0, 'Portfolio_Pct': 12.0, 'Portfolio_Pct_Rank': 2, 'Fund_Concentration_Ratio': 40.0, 'Shares_Delta_Pct': 0},
        ])


    def test_kpi_calculations(self):
        # 1. Test Flags
        df_flags = _calculate_fund_level_flags(self.df_fund)
        
        # Verify TSLA in FundA is high conviction
        tsla_a = df_flags[(df_flags['Fund'] == 'FundA') & (df_flags['Ticker'] == 'TSLA')].iloc[0]
        self.assertTrue(tsla_a['is_high_conviction'])
        
        # Verify TSLA in FundB is NOT high conviction (even if NEW, rank/pct too low)
        tsla_b = df_flags[(df_flags['Fund'] == 'FundB') & (df_flags['Ticker'] == 'TSLA')].iloc[0]
        self.assertFalse(tsla_b['is_high_conviction'])
        
        # Verify TSLA in FundC is NOT high conviction (not NEW)
        tsla_c = df_flags[(df_flags['Fund'] == 'FundC') & (df_flags['Ticker'] == 'TSLA')].iloc[0]
        self.assertFalse(tsla_c['is_high_conviction'])

        # 2. Test Aggregation
        df_agg = _aggregate_stock_data(df_flags)
        
        tsla_summary = df_agg[df_agg['Ticker'] == 'TSLA'].iloc[0]
        
        # High_Conviction_Count should be 1 (only FundA)
        self.assertEqual(tsla_summary['High_Conviction_Count'], 1)
        
        # Avg_Fund_Concentration: (40 + 30 + 50) / 3 = 40.0
        self.assertEqual(tsla_summary['Avg_Fund_Concentration'], 40.0)
        
        # Ownership_Delta_Avg: FundC increased by 50%. A and B were NEW (excluded). So mean of [50] = 50.0
        self.assertEqual(tsla_summary['Ownership_Delta_Avg'], 50.0)

        # 3. Test Derived Metrics
        df_derived = _calculate_derived_metrics(df_agg)
        tsla_final = df_derived[df_derived['Ticker'] == 'TSLA'].iloc[0]
        
        self.assertEqual(tsla_final['Portfolio_Concentration_Avg'], 40.0)
        self.assertIn('High_Conviction_Count', tsla_final)
        self.assertIn('Ownership_Delta_Avg', tsla_final)


if __name__ == '__main__':
    unittest.main()

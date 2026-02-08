from app.analysis.performance_evaluator import PerformanceEvaluator
import pandas as pd
import unittest
from unittest.mock import patch


class TestPerformanceEvaluator(unittest.TestCase):

    @patch('app.analysis.performance_evaluator.load_fund_holdings')
    @patch('app.analysis.performance_evaluator.get_previous_quarter')
    @patch('app.analysis.performance_evaluator.get_quarter_date')
    @patch('app.analysis.performance_evaluator.PriceFetcher.get_avg_price')
    def test_calculate_quarterly_performance_success(self, mock_get_avg_price, mock_get_quarter_date, mock_get_prev_quarter, mock_load_holdings):
        """
        Tests calculation with all data available and no missing prices.
        """
        mock_get_prev_quarter.return_value = "2024Q4"
        mock_get_quarter_date.return_value = "2025-03-31"
        
        # Previous quarter holdings (start of quarter)
        df_prev = pd.DataFrame([
            {'CUSIP': 'C1', 'Ticker': 'T1', 'Company': 'Co1', 'Shares': 100, 'Value': 1000, 'Reported_Price': 10.0},
            {'CUSIP': 'C2', 'Ticker': 'T2', 'Company': 'Co2', 'Shares': 200, 'Value': 2000, 'Reported_Price': 10.0}
        ])
        
        # Current quarter holdings (end of quarter)
        df_curr = pd.DataFrame([
            {'CUSIP': 'C1', 'Shares': 100, 'Value': 1100, 'Reported_Price': 11.0},
            {'CUSIP': 'C2', 'Shares': 200, 'Value': 1800, 'Reported_Price': 9.0}
        ])
        
        def side_effect(fund, quarter):
            if quarter == "2024Q4": return df_prev
            if quarter == "2025Q1": return df_curr
            return pd.DataFrame()
        
        mock_load_holdings.side_effect = side_effect
        
        result = PerformanceEvaluator.calculate_quarterly_performance("Test Fund", "2025Q1")
        
        # Total Value = 3000
        # W1 = 1/3, R1 = 0.1, WR1 = 0.0333
        # W2 = 2/3, R2 = -0.1, WR2 = -0.0666
        # Portfolio Return = -0.0333...
        
        self.assertEqual(result['fund'], "Test Fund")
        self.assertEqual(result['quarter'], "2025Q1")
        self.assertAlmostEqual(result['portfolio_return'], -3.333333333333333)
        self.assertEqual(len(result['top_contributors']), 2)
        self.assertEqual(result['top_contributors'][0]['Ticker'], 'T1')


    @patch('app.analysis.performance_evaluator.load_fund_holdings')
    @patch('app.analysis.performance_evaluator.get_previous_quarter')
    @patch('app.analysis.performance_evaluator.get_quarter_date')
    @patch('app.analysis.performance_evaluator.PriceFetcher.get_avg_price')
    def test_calculate_quarterly_performance_closed_position(self, mock_get_avg_price, mock_get_quarter_date, mock_get_prev_quarter, mock_load_holdings):
        """
        Tests calculation where a position is closed (not in current report) and price is fetched.
        """
        mock_get_prev_quarter.return_value = "2024Q4"
        mock_get_quarter_date.return_value = "2025-03-31"
        mock_get_avg_price.return_value = 12.0 # Fetched price for closed position
        
        df_prev = pd.DataFrame([
            {'CUSIP': 'C1', 'Ticker': 'T1', 'Company': 'Co1', 'Shares': 100, 'Value': 1000, 'Reported_Price': 10.0}
        ])
        
        df_curr = pd.DataFrame() # Position C1 is closed, so no data in 2025Q1
        # Wait, if df_curr is empty, the function returns an error early. Let's provide a dummy other row.
        df_curr = pd.DataFrame([{'CUSIP': 'OTHER', 'Shares': 10, 'Value': 100, 'Reported_Price': 10.0}])
        
        def side_effect(fund, quarter):
            if quarter == "2024Q4": return df_prev
            if quarter == "2025Q1": return df_curr
            return pd.DataFrame()
        
        mock_load_holdings.side_effect = side_effect
        
        result = PerformanceEvaluator.calculate_quarterly_performance("Test Fund", "2025Q1")
        
        # Price start = 10.0, Price end = 12.0 (fetched) -> Return = 0.2
        self.assertAlmostEqual(result['portfolio_return'], 20.0)
        mock_get_avg_price.assert_called_once()


    @patch('app.analysis.performance_evaluator.load_fund_holdings')
    def test_calculate_quarterly_performance_missing_data(self, mock_load_holdings):
        mock_load_holdings.return_value = pd.DataFrame()
        result = PerformanceEvaluator.calculate_quarterly_performance("Test Fund", "2025Q1")
        self.assertIn("error", result)
        self.assertIn("Missing data", result['error'])


if __name__ == '__main__':
    unittest.main()

from app.analysis.quarterly_report import generate_comparison
from app.utils.strings import format_percentage, format_value
from unittest.mock import patch
import pandas as pd
import unittest


@patch("app.analysis.quarterly_report.resolve_ticker")
class TestReport(unittest.TestCase):

    def test_generate_comparison(self, mock_resolve_ticker):
        def resolve_ticker(df):
            ticker_map = {
                "TC123456": "TSLA",
                "TC789012": "GOOGL",
                "TC345678": "AMZN",
                "TC901234": "MSFT"
            }
            df['Ticker'] = df['CUSIP'].map(ticker_map)
            return df
        mock_resolve_ticker.side_effect = resolve_ticker

        # Create mock DataFrames with multiple stocks
        df_recent = pd.DataFrame([
            {"CUSIP": "TC123456", "Company": "Tesla", "Shares": 1000, "Value": 25000},      # TSLA - Increased
            {"CUSIP": "TC789012", "Company": "Google", "Shares": 200, "Value": 5000},       # GOOGL - New
            {"CUSIP": "TC901234", "Company": "Microsoft", "Shares": 400, "Value": 8000}     # MSFT - No change
        ])
        df_previous = pd.DataFrame([
            {"CUSIP": "TC123456", "Company": "Tesla", "Shares": 500, "Value": 10000},
            {"CUSIP": "TC345678", "Company": "Amazon", "Shares": 300, "Value": 6000},       # AMZN - Closed
            {"CUSIP": "TC901234", "Company": "Microsoft", "Shares": 400, "Value": 8000}
        ])

        df_output = generate_comparison(df_recent, df_previous)

        # The function sorts by ['Delta_Value', 'Value'] descending.
        # Expected order: TSLA, GOOGL, MSFT, AMZN, Total
        
        # Assertions for Stock 1 (TSLA - Increased) - Index 0
        self.assertEqual(df_output.loc[0, 'CUSIP'], "TC123456")
        self.assertEqual(df_output.loc[0, 'Ticker'], "TSLA")
        self.assertEqual(df_output.loc[0, 'Shares'], 1000)
        self.assertEqual(df_output.loc[0, 'Delta_Shares'], 500)
        self.assertEqual(df_output.loc[0, 'Value'], format_value(25000))
        # Delta_Value = Delta_Shares * Price_per_Share_recent = (1000 - 500) * (25000 / 1000) = 500 * 25 = 12500
        self.assertEqual(df_output.loc[0, 'Delta_Value'], format_value(12500)) 
        self.assertEqual(df_output.loc[0, 'Delta'], format_percentage(100, True))
        self.assertEqual(df_output.loc[0, 'Portfolio%'], format_percentage((25000/38000)*100))

        # Assertions for Stock 2 (GOOGL - New) - Index 1
        self.assertEqual(df_output.loc[1, 'CUSIP'], "TC789012")
        self.assertEqual(df_output.loc[1, 'Ticker'], "GOOGL")
        self.assertEqual(df_output.loc[1, 'Shares'], 200)
        self.assertEqual(df_output.loc[1, 'Delta_Shares'], 200)
        self.assertEqual(df_output.loc[1, 'Value'], format_value(5000))
        self.assertEqual(df_output.loc[1, 'Delta_Value'], format_value(5000))
        self.assertEqual(df_output.loc[1, 'Delta'], "NEW")
        self.assertEqual(df_output.loc[1, 'Portfolio%'], format_percentage((5000/38000)*100))

        # Assertions for Stock 3 (MSFT - No Change) - Index 2
        self.assertEqual(df_output.loc[2, 'CUSIP'], "TC901234")
        self.assertEqual(df_output.loc[2, 'Ticker'], "MSFT")
        self.assertEqual(df_output.loc[2, 'Shares'], 400)
        self.assertEqual(df_output.loc[2, 'Delta_Shares'], 0)
        self.assertEqual(df_output.loc[2, 'Value'], format_value(8000))
        self.assertEqual(df_output.loc[2, 'Delta_Value'], format_value(0))
        self.assertEqual(df_output.loc[2, 'Delta'], "NO CHANGE")
        self.assertEqual(df_output.loc[2, 'Portfolio%'], format_percentage((8000/38000)*100))

        # Assertions for Stock 4 (AMZN - Closed) - Index 3
        self.assertEqual(df_output.loc[3, 'CUSIP'], "TC345678")
        self.assertEqual(df_output.loc[3, 'Ticker'], "AMZN")
        self.assertEqual(df_output.loc[3, 'Shares'], 0)
        self.assertEqual(df_output.loc[3, 'Delta_Shares'], -300)
        self.assertEqual(df_output.loc[3, 'Value'], format_value(0))
        self.assertEqual(df_output.loc[3, 'Delta_Value'], format_value(-6000))
        self.assertEqual(df_output.loc[3, 'Delta'], "CLOSE")
        self.assertEqual(df_output.loc[3, 'Portfolio%'], format_percentage(0))

        total_row_index = len(df_output) - 1
        self.assertEqual(df_output.loc[total_row_index, 'CUSIP'], "Total")
        # Total Portfolio Value (Recent): 25000 + 5000 + 8000 = 38000
        self.assertEqual(df_output.loc[total_row_index, 'Value'], format_value(38000))
        # Total Delta Value: 12500 + 5000 - 6000 + 0 = 11500
        self.assertEqual(df_output.loc[total_row_index, 'Delta_Value'], format_value(11500))
        # Total Delta %: total_delta_value / previous_portfolio_value * 100 = 11500 / (10000 + 6000 + 8000) * 100 = 11500 / 24000 * 100
        self.assertEqual(df_output.loc[total_row_index, 'Delta'], format_percentage((11500/24000)*100, True))
        self.assertEqual(df_output.loc[total_row_index, 'Portfolio%'], format_percentage(100))


if __name__ == '__main__':
    unittest.main()
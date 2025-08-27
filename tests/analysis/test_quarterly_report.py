from app.analysis.quarterly_report import generate_comparison
from app.utils.strings import format_percentage, format_value
from unittest.mock import patch
import pandas as pd
import unittest


@patch("app.analysis.quarterly_report.resolve_ticker")
class TestReport(unittest.TestCase):

    def test_generate_comparison(self, mock_resolve_ticker):
        def mock_side_effect(df):
            df['Ticker'] = 'TEST'
            return df
        mock_resolve_ticker.side_effect = mock_side_effect

        # Create mock DataFrames
        df_recent = pd.DataFrame([{"CUSIP": "TC123456", "Company": "Test Company", "Shares": 1000, "Value": 18000 }])
        df_previous = pd.DataFrame([{"CUSIP": "TC123456", "Company": "Test Company", "Shares": 500, "Value": 10000 }])

        df_output = generate_comparison(df_recent, df_previous)

        self.assertEqual(df_output.iloc[0]['CUSIP'], "TC123456")
        self.assertEqual(df_output.iloc[0]['Delta'], format_percentage(100, True))
        self.assertEqual(df_output.iloc[0]['Delta_Value'], format_value(9000))

        self.assertEqual(df_output.iloc[1]['CUSIP'], "Total")
        self.assertEqual(df_output.iloc[1]['Delta'], format_percentage(80, True))
        self.assertEqual(df_output.iloc[1]['Delta_Value'], format_value(8000))


if __name__ == '__main__':
    unittest.main()
from scraper.pandas_processor import generate_comparison, xml_to_dataframe_13f
from scraper.string_utils import format_percentage, format_value
from unittest.mock import patch
import pandas as pd
import unittest

class TestPandasProcessor(unittest.TestCase):

    def test_xml_to_dataframe_13f(self):
        # Mock XML content
        xml_content = """
        <infotable>
            <nameofissuer>Test Company</nameofissuer>
            <cusip>123456789</cusip>
            <value>1000</value>
            <shrsorprnamt>
                <sshprnamt>100</sshprnamt>
            </shrsorprnamt>
        </infotable>
        """
       
        # Call the function
        df = xml_to_dataframe_13f(xml_content)
        
        # Assertions
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 1)
        self.assertEqual(df['Company'][0], 'Test Company')
        self.assertEqual(df['CUSIP'][0], '123456789')
        self.assertEqual(df['Value'][0], 1000)
        self.assertEqual(df['Shares'][0], 100)


    def test_generate_comparison(self):
        # Create mock DataFrames
        df_recent = pd.DataFrame([{"CUSIP": "TC123456", "Company": "Test Company", "Shares": 1000, "Value": 18000 }])
        df_previous = pd.DataFrame([{"CUSIP": "TC123456", "Company": "Test Company", "Shares": 500, "Value": 10000 }])

        def mock_resolve_ticker(df):
            df['Ticker'] = 'TEST'
            return df

        with patch("scraper.pandas_processor.resolve_ticker", side_effect=mock_resolve_ticker):
            df_output = generate_comparison(df_recent, df_previous)
            
            self.assertEqual(df_output.iloc[0]['CUSIP'], "TC123456")
            self.assertEqual(df_output.iloc[0]['Delta'], format_percentage(100, True))
            self.assertEqual(df_output.iloc[0]['Delta_Value'], format_value(9000))
            
            self.assertEqual(df_output.iloc[1]['CUSIP'], "Total")
            self.assertEqual(df_output.iloc[1]['Delta'], format_percentage(80, True))
            self.assertEqual(df_output.iloc[1]['Delta_Value'], format_value(8000))


if __name__ == '__main__':
    unittest.main()
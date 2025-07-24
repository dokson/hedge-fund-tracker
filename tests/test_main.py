import unittest
import os
import pandas as pd
from scraper.main import xml_to_dataframe, generate_comparison
from unittest.mock import patch

class TestMain(unittest.TestCase):

    def test_xml_to_dataframe(self):
        # Mock XML content
        xml_content = """
        <infotable>
            <nameofissuer>Test Issuer</nameofissuer>
            <cusip>123456789</cusip>
            <value>1000</value>
            <shrsorprnamt>
                <sshprnamt>100</sshprnamt>
            </shrsorprnamt>
        </infotable>
        """
       
        # Call the function
        df = xml_to_dataframe(xml_content)
        
        # Assertions
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 1)
        self.assertEqual(df['Name of Issuer'][0], 'Test Issuer')
        self.assertEqual(df['CUSIP'][0], '123456789')
        self.assertEqual(df['Value'][0], 1000)
        self.assertEqual(df['Shares'][0], 100)

    @patch('scraper.main.get_cusip_to_ticker_mapping_finnhub_with_fallback')
    def test_generate_comparison(self, mock_get_tickers):
        # Create mock DataFrames
        data1 = {'Name of Issuer': ['Test Issuer'], 'CUSIP': ['TC123456'], 'Value': [1000], 'Shares': [100]}
        data2 = {'Name of Issuer': ['Test Issuer'], 'CUSIP': ['TC123456'], 'Value': [500], 'Shares': [50]}
        df_recent = pd.DataFrame(data1)
        df_previous = pd.DataFrame(data2)
        cik = "0123456789"
        filing_dates = ["1234-05-06", "0123-04-05"]
        filename = f"{cik}_{filing_dates[0]}.csv"

        # Mock the return value of the ticker mapping function
        mock_get_tickers.return_value = pd.Series(['TEST'], index=['TC123456'])

        # Call the function
        generate_comparison(cik, filing_dates, df_recent, df_previous)
        self.assertTrue(os.path.exists(filename))

        # Add assertions to check the output file
        df_comparison = pd.read_csv(f"{cik}_{filing_dates[0]}.csv")
        self.assertEqual(df_comparison['Delta_%'][0], '+100.0%')
        self.assertEqual(df_comparison['Ticker'][0], 'TEST')


        # Clean up: remove the file
        os.remove(filename)

if __name__ == '__main__':
    unittest.main()
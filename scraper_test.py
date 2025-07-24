import unittest
import pandas as pd
from bs4 import BeautifulSoup
import os
from scraper import create_url, xml_to_dataframe, generate_comparison

class TestScraper(unittest.TestCase):

    def test_create_url(self):
        cik = "1234567890"
        expected_url = f'https://www.sec.gov/cgi-bin/browse-edgar?CIK={cik}&owner=exclude&action=getcompany&type=13F-HR'
        self.assertEqual(create_url(cik), expected_url)

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
        soup_xml = BeautifulSoup(xml_content, "xml")
        
        # Call the function
        df = xml_to_dataframe(soup_xml)
        
        # Assertions
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 1)
        self.assertEqual(df['Name of Issuer'][0], 'Test Issuer')
        self.assertEqual(df['CUSIP'][0], '123456789')
        self.assertEqual(df['Value'][0], 1000)
        self.assertEqual(df['Shares'][0], 100)


    def test_generate_comparison(self):
        # Create mock DataFrames
        data1 = {'Name of Issuer': ['Test Issuer'], 'CUSIP': ['123456789'], 'Value': [1000], 'Shares': [100]}
        data2 = {'Name of Issuer': ['Test Issuer'], 'CUSIP': ['123456789'], 'Value': [500], 'Shares': [50]}
        df_recent = pd.DataFrame(data1)
        df_previous = pd.DataFrame(data2)
        cik = "1234567890"
        filing_dates = ["1234-05-06"]
        filename = f"{cik}_{filing_dates[0]}.csv"

        # Call the function
        generate_comparison(cik, filing_dates, df_recent, df_previous)
        self.assertTrue(os.path.exists(filename))

        # Add assertions to check the output file
        df_actual = pd.read_csv(f"{cik}_{filing_dates[0]}.csv")
        self.assertEqual(df_actual['Percentage Change'][0], '+100.0%')

        # Clean up: remove the file
        os.remove(filename)

if __name__ == '__main__':
    unittest.main()
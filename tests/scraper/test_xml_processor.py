from app.scraper.xml_processor import xml_to_dataframe_13f
import pandas as pd
import unittest

class TestXmlProcessor(unittest.TestCase):

    def test_xml_to_dataframe_13f_full_dollars_no_scaling(self):
        """
        Tests that values are NOT scaled if the implied share price is realistic (Full Dollars).
        Example: VanEck style.
        """
        # 10,000,000 / 100,000 shares = $100 per share (Realistic price)
        xml_content = """
        <informationtable>
            <infotable>
                <nameofissuer>VanEck Example Corp</nameofissuer>
                <cusip>123456789</cusip>
                <value>10000000</value>
                <shrsorprnamt><sshprnamt>100000</sshprnamt></shrsorprnamt>
            </infotable>
        </informationtable>
        """
        
        df = xml_to_dataframe_13f(xml_content)
        
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 1)
        # Value should remain exactly as reported
        self.assertEqual(df['Value'][0], 10000000)
        self.assertEqual(df['Shares'][0], 100000)


    def test_xml_to_dataframe_13f_thousands_with_scaling(self):
        """
        Tests that values ARE scaled by 1000 if the implied share price is suspiciously low.
        Example: Duquesne style.
        """
        # 50,000 / 500,000 shares = $0.10 per share (Suspiciously low, likely in thousands)
        # After scaling: $50,000,000 / 500,000 = $100 per share
        xml_content = """
        <informationtable>
            <infotable>
                <nameofissuer>Duquesne Example Inc</nameofissuer>
                <cusip>987654321</cusip>
                <value>50000</value>
                <shrsorprnamt><sshprnamt>500000</sshprnamt></shrsorprnamt>
            </infotable>
        </informationtable>
        """
        
        df = xml_to_dataframe_13f(xml_content)
        
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 1)
        # Value should be multiplied by 1000
        self.assertEqual(df['Value'][0], 50000 * 1000)
        self.assertEqual(df['Shares'][0], 500000)


    def test_xml_to_dataframe_13f_mixed_portfolio_median_logic(self):
        """
        Tests that the scaling decision is based on the MEDIAN price of the portfolio.
        """
        xml_content = """
        <informationtable>
            <infotable>
                <nameofissuer>Stock A</nameofissuer>
                <cusip>CUSIP1</cusip>
                <value>100</value> <shrsorprnamt><sshprnamt>1000</sshprnamt></shrsorprnamt>
            </infotable>
            <infotable>
                <nameofissuer>Stock B</nameofissuer>
                <cusip>CUSIP2</cusip>
                <value>200</value> <shrsorprnamt><sshprnamt>2000</sshprnamt></shrsorprnamt>
            </infotable>
            <infotable>
                <nameofissuer>Expensive Outlier</nameofissuer>
                <cusip>CUSIP3</cusip>
                <value>5000</value> <shrsorprnamt><sshprnamt>10</sshprnamt></shrsorprnamt>
            </infotable>
        </informationtable>
        """
        # Prices: [0.1, 0.1, 500.0]. Median is 0.1. 
        # 0.1 < 0.5 threshold -> Should scale everything by 1000.
        df = xml_to_dataframe_13f(xml_content)
        
        # 'Stock A' value should be 100 * 1000 = 100,000
        val_a = df.loc[df['Company'] == 'Stock A', 'Value'].values[0]
        self.assertEqual(val_a, 100000)


if __name__ == '__main__':
    unittest.main()
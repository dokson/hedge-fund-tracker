from app.scraper.xml_processor import xml_to_dataframe_13f
import pandas as pd
import unittest


class TestXmlProcessor(unittest.TestCase):

    def test_xml_to_dataframe_13f_no_scaling(self):
        """
        Tests that values are NOT scaled if they are large (i.e., already in full dollars).
        """
        # Mock XML content with a value > MAX_POSITION_THRESHOLD (1M)
        xml_content = """
        <informationtable>
            <infotable>
                <nameofissuer>Big Value Corp</nameofissuer>
                <cusip>123456789</cusip>
                <value>10000000</value>
                <shrsorprnamt><sshprnamt>100</sshprnamt></shrsorprnamt>
            </infotable>
        </informationtable>
        """
       
        df = xml_to_dataframe_13f(xml_content)
        
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 1)
        self.assertEqual(df['Company'][0], 'Big Value Corp')
        self.assertEqual(df['CUSIP'][0], '123456789')
        self.assertEqual(df['Value'][0], 10000000)
        self.assertEqual(df['Shares'][0], 100)


    def test_xml_to_dataframe_13f_with_scaling(self):
        """
        Tests that values ARE scaled by 1000 if they are small (i.e. reported in thousands).
        """
        # Mock XML content with a value < MAX_POSITION_THRESHOLD (1M)
        xml_content = """
        <informationtable>
            <infotable>
                <nameofissuer>Small Value Inc</nameofissuer>
                <cusip>987654321</cusip>
                <value>50000</value>
                <shrsorprnamt><sshprnamt>500</sshprnamt></shrsorprnamt>
            </infotable>
        </informationtable>
        """
       
        df = xml_to_dataframe_13f(xml_content)
        
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 1)
        self.assertEqual(df['Company'][0], 'Small Value Inc')
        self.assertEqual(df['CUSIP'][0], '987654321')
        self.assertEqual(df['Value'][0], 50000 * 1000)
        self.assertEqual(df['Shares'][0], 500)


if __name__ == '__main__':
    unittest.main()
from app.scraper.xml_processor import xml_to_dataframe_13f
import pandas as pd
import unittest


class TestXmlProcessor(unittest.TestCase):

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


if __name__ == '__main__':
    unittest.main()
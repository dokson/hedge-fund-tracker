from app.utils.gics import load_standard_sectors, load_yf_sectors, load_industry_groups, load_industries, load_sub_industries
import pandas as pd
import unittest


class TestGICS(unittest.TestCase):
    def test_load_standard_sectors(self):
        """
        Tests the load_standard_sectors method.
        """
        df = load_standard_sectors()
        self.assertIsInstance(df, pd.DataFrame)
        self.assertFalse(df.empty)
        self.assertIn('Sector Code', df.columns)
        self.assertIn('Sector', df.columns)
        self.assertEqual(len(df), 11, "There should be exactly 11 GICS sectors")


    def test_load_yf_sectors(self):
        """
        Tests the load_yf_sectors method.
        """
        df = load_yf_sectors()
        self.assertIsInstance(df, pd.DataFrame)
        self.assertFalse(df.empty)
        self.assertIn('Key', df.columns)
        self.assertIn('Name', df.columns)
        self.assertEqual(len(df), 11, "There should be exactly 11 GICS sectors")


    def test_load_industry_groups(self):
        """
        Tests the load_industry_groups method.
        """
        df = load_industry_groups()
        self.assertIsInstance(df, pd.DataFrame)
        self.assertFalse(df.empty)
        self.assertIn('Industry Group Code', df.columns)
        self.assertIn('Industry Group', df.columns)
        # GICS typically has 25 industry groups
        self.assertGreaterEqual(len(df), 24) 


    def test_load_industries(self):
        """
        Tests the load_industries method.
        """
        df = load_industries()
        self.assertIsInstance(df, pd.DataFrame)
        self.assertFalse(df.empty)
        self.assertIn('Industry Code', df.columns)
        self.assertIn('Industry', df.columns)
        # GICS typically has ~74 industries
        self.assertGreaterEqual(len(df), 70)


    def test_load_sub_industries(self):
        """
        Tests the load_sub_industries method.
        """
        df = load_sub_industries()
        self.assertIsInstance(df, pd.DataFrame)
        self.assertFalse(df.empty)
        self.assertIn('Sub-Industry Code', df.columns)
        self.assertIn('Sub-Industry', df.columns)
        # GICS typically has ~163 sub-industries
        self.assertGreaterEqual(len(df), 160)


if __name__ == '__main__':
    unittest.main()

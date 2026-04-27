from app.utils.gics import (
    load_industries,
    load_industry_groups,
    load_standard_sectors,
    load_sub_industries,
    load_yf_sectors,
)
import pandas as pd
import unittest


class TestGICS(unittest.TestCase):

    def test_loaders_return_expected_dataframes(self):
        """
        Each GICS loader must return a non-empty DataFrame containing the
        expected code/name columns and at least the documented number of rows.
        """
        cases = [
            (load_standard_sectors, ['Sector Code', 'Sector'], 11, True),
            (load_yf_sectors, ['Key', 'Name'], 11, True),
            (load_industry_groups, ['Industry Group Code', 'Industry Group'], 24, False),
            (load_industries, ['Industry Code', 'Industry'], 70, False),
            (load_sub_industries, ['Sub-Industry Code', 'Sub-Industry'], 160, False),
        ]

        for loader, expected_columns, min_rows, exact in cases:
            with self.subTest(loader=loader.__name__):
                df = loader()
                self.assertIsInstance(df, pd.DataFrame)
                self.assertFalse(df.empty)
                for column in expected_columns:
                    self.assertIn(column, df.columns)
                if exact:
                    self.assertEqual(len(df), min_rows)
                else:
                    self.assertGreaterEqual(len(df), min_rows)


if __name__ == '__main__':
    unittest.main()

from app.utils.database import DB_FOLDER, get_all_quarters
import pandas as pd
import os
import unittest

EXCLUDED_HEDGE_FUNDS_FILE = 'excluded_hedge_funds.csv'


class TestHedgeFunds(unittest.TestCase):
    def test_no_files_for_excluded_funds(self):
        """
        Verifies that no report files exist for any of the excluded funds in any of the quarterly report directories.
        """
        try:
            excluded_funds_df = pd.read_csv(f"{DB_FOLDER}/{EXCLUDED_HEDGE_FUNDS_FILE}")
        except FileNotFoundError:
            self.fail(f"{EXCLUDED_HEDGE_FUNDS_FILE} not found.")

        excluded_fund_names = excluded_funds_df['Fund'].str.replace(' ', '_').tolist()
        all_quarters = get_all_quarters()

        found_files = []

        for quarter in all_quarters:
            quarter_path = os.path.join(DB_FOLDER, quarter)
            for fund_name in excluded_fund_names:
                file_path = os.path.join(quarter_path, f"{fund_name}.csv")
                if os.path.exists(file_path):
                    found_files.append(file_path)

        self.assertEqual(len(found_files), 0, f"Found unexpected files for excluded funds: {found_files}")

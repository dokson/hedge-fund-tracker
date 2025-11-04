from app.utils.database import DB_FOLDER, get_all_quarters, get_last_quarter_for_fund, load_hedge_funds
import os
import unittest


class TestHedgeFunds(unittest.TestCase):
    def test_all_reports_belong_to_hedge_funds_file(self):
        """
        Verifies that all quarterly report files correspond to a fund listed in hedge_funds.csv.
        """
        hedge_funds = load_hedge_funds()
        known_fund_names = {fund['Fund'] for fund in hedge_funds}
        all_quarters = get_all_quarters()

        unexpected_files = []

        for quarter in all_quarters:
            quarter_path = os.path.join(DB_FOLDER, quarter)
            if not os.path.isdir(quarter_path):
                continue

            for filename in os.listdir(quarter_path):
                if filename.endswith('.csv'):
                    fund_name_from_file = os.path.splitext(filename)[0].replace('_', ' ')
                    if fund_name_from_file not in known_fund_names:
                        unexpected_files.append(os.path.join(quarter_path, filename))

        self.assertEqual(len(unexpected_files), 0, f"Found report files for unknown funds: {unexpected_files}")


    def test_all_funds_have_at_least_one_report(self):
        """
        Verifies that every fund listed in hedge_funds.csv has at least one quarterly report file.
        """
        hedge_funds = load_hedge_funds()
        funds_without_reports = []

        for fund in hedge_funds:
            fund_name = fund['Fund']
            if get_last_quarter_for_fund(fund_name) is None:
                funds_without_reports.append(fund_name)

        if funds_without_reports:
            self.fail(f"Found {len(funds_without_reports)} funds in hedge_funds.csv with no corresponding report files in any quarter:\n{funds_without_reports}")

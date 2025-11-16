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

        if unexpected_files:
            formatted_files = "\n".join(sorted(unexpected_files))
            error_message = (
                f"Found {len(unexpected_files)} report files for unknown funds.\n"
                "These files correspond to funds not listed in hedge_funds.csv. Please add them or remove the files:\n\n"
                f"{formatted_files}"
            )
            self.fail(error_message)


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
            formatted_funds = "\n".join(sorted(funds_without_reports))
            error_message = (
                f"Found {len(funds_without_reports)} funds in hedge_funds.csv with no corresponding report files in any quarter.\n"
                "Please generate a report for them or remove them from hedge_funds.csv:\n\n"
                f"{formatted_funds}"
            )
            self.fail(error_message)

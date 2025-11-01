from app.utils.readme import EXCLUDED_HEDGE_FUNDS_FILE, generate_excluded_funds_list
import pandas as pd
import unittest
from unittest.mock import patch


class TestReadme(unittest.TestCase):
    @patch('app.utils.readme.pd.read_csv')
    def test_generate_excluded_funds_list_success(self, mock_read_csv):
        """
        Tests successful generation of the markdown list from a mock CSV.
        """
        # 1. Setup: Create a mock DataFrame with different scenarios
        mock_data = {
            'Manager': ['Warren Buffett', 'Ken Griffin', 'BlackRock'],
            'Fund': ['Berkshire Hathaway', 'Citadel Advisors', 'BlackRock'],
            'URL': ['url1', 'url2', 'url3']
        }
        mock_df = pd.DataFrame(mock_data)
        mock_read_csv.return_value = mock_df

        # 2. Execute: Call the function
        result = generate_excluded_funds_list()

        # 3. Assert: Check if the output is the expected markdown string
        expected_output = (
            "- *Warren Buffett*'s [Berkshire Hathaway](url1)\n"
            "- *Ken Griffin*'s [Citadel Advisors](url2)\n"
            "- [BlackRock](url3)"
        )
        self.assertEqual(result, expected_output)
        mock_read_csv.assert_called_once_with(EXCLUDED_HEDGE_FUNDS_FILE, keep_default_na=False)


    @patch('app.utils.readme.pd.read_csv')
    @patch('builtins.print')
    def test_generate_excluded_funds_list_file_not_found(self, mock_print, mock_read_csv):
        """
        Tests that the function returns None and prints an error when the CSV file is not found.
        """
        mock_read_csv.side_effect = FileNotFoundError
        result = generate_excluded_funds_list()
        self.assertIsNone(result)
        mock_print.assert_called_with(f"❌ Error: {EXCLUDED_HEDGE_FUNDS_FILE} was not found.")

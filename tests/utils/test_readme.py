import unittest
from unittest.mock import patch

import pandas as pd

from app.utils.readme import EXCLUDED_HEDGE_FUNDS_FILE, generate_excluded_funds_list


class TestReadme(unittest.TestCase):
    @patch("app.utils.readme.pd.read_csv")
    def test_generate_excluded_funds_list_success(self, mock_read_csv):
        """
        Tests successful generation of the markdown list from a mock CSV.
        """
        # 1. Setup: Create a mock DataFrame with different scenarios
        mock_data = {
            "Manager": ["Warren Buffett", "Ken Griffin", "BlackRock"],
            "Fund": ["Berkshire Hathaway", "Citadel Advisors", "BlackRock"],
            "URL": ["url1", "url2", "url3"],
        }
        mock_df = pd.DataFrame(mock_data)
        mock_read_csv.return_value = mock_df

        # 2. Execute: Call the function
        result = generate_excluded_funds_list()

        # 3. Assert: Check if the output is the expected markdown string
        expected_output = (
            "- _Warren Buffett_'s [Berkshire Hathaway](url1)\n"
            "- _Ken Griffin_'s [Citadel Advisors](url2)\n"
            "- [BlackRock](url3)"
        )
        self.assertEqual(result, expected_output)
        mock_read_csv.assert_called_once_with(EXCLUDED_HEDGE_FUNDS_FILE, keep_default_na=False)

    @patch("app.utils.readme.pd.read_csv")
    def test_generate_excluded_funds_list_file_not_found(self, mock_read_csv):
        """
        Tests that the function returns None and logs an error when the CSV file is not found.
        """
        mock_read_csv.side_effect = FileNotFoundError
        with self.assertLogs("app.utils.readme", level="ERROR") as cm:
            result = generate_excluded_funds_list()
        self.assertIsNone(result)
        self.assertIn(EXCLUDED_HEDGE_FUNDS_FILE, "\n".join(cm.output))

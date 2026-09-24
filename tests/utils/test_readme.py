import unittest
from unittest.mock import patch

import pandas as pd

from app.utils.readme import EXCLUDED_HEDGE_FUNDS_FILE, generate_excluded_funds_list, update_readme


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

    @patch("app.utils.readme.atomic_write_text")
    @patch("app.utils.readme.generate_excluded_funds_list")
    def test_update_readme_keeps_backslashes_literal(self, mock_list, mock_write):
        """
        Backslashes in fund names must not be read as regex group references.
        """
        import tempfile
        from pathlib import Path

        mock_list.return_value = r"- [Fund \1 \g<0>](url)"
        with tempfile.TemporaryDirectory() as tmp:
            readme = Path(tmp) / "README.md"
            readme.write_text(
                "a\n<!-- EXCLUDED_FUNDS_LIST_START -->old<!-- EXCLUDED_FUNDS_LIST_END -->\nb",
                encoding="utf-8",
                newline="",
            )
            with patch("app.utils.readme.README_FILE", str(readme)):
                update_readme()
        mock_write.assert_called_once()
        self.assertEqual(
            mock_write.call_args.args[1],
            "a\n<!-- EXCLUDED_FUNDS_LIST_START -->\n"
            r"- [Fund \1 \g<0>](url)"
            "\n<!-- EXCLUDED_FUNDS_LIST_END -->\nb",
        )

    @patch("app.utils.readme.atomic_write_text")
    @patch("app.utils.readme.generate_excluded_funds_list")
    def test_update_readme_keeps_crlf_line_endings_consistent(self, mock_list, mock_write):
        """
        A CRLF checkout must not come back with the inserted lines in bare LF.
        """
        import tempfile
        from pathlib import Path

        mock_list.return_value = "- [Fund A](url)\n- [Fund B](url)"
        with tempfile.TemporaryDirectory() as tmp:
            readme = Path(tmp) / "README.md"
            readme.write_text(
                "a\r\n<!-- EXCLUDED_FUNDS_LIST_START -->old<!-- EXCLUDED_FUNDS_LIST_END -->\r\nb\r\n",
                encoding="utf-8",
                newline="",
            )
            with patch("app.utils.readme.README_FILE", str(readme)):
                update_readme()
        written = mock_write.call_args.args[1]
        self.assertEqual(written.count("\n"), written.count("\r\n"))
        self.assertIn("- [Fund A](url)\r\n- [Fund B](url)", written)

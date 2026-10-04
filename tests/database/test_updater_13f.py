"""
Tests for the updater's 13F comparison path.
"""

import unittest
from unittest.mock import patch

from database.updater import process_fund


def _filing(ref: str, published: str, kind: str = "") -> dict:
    """
    A scraped 13F filing.
    """
    return {"reference_date": ref, "date": published, "xml_content": b"", "amendment_type": kind}


@patch("database.updater.save_comparison")
@patch("database.updater.generate_comparison")
@patch("database.updater.load_split_factors", return_value={})
@patch("database.updater.corrections_for", return_value={})
@patch("database.updater.xml_to_dataframe_13f")
@patch("database.updater.fetch_latest_two_13f_filings")
class TestProcessFundAmendments(unittest.TestCase):
    """
    Both sides of a comparison are completed when they are NEW HOLDINGS amendments.
    """

    def test_both_filings_go_through_complete_new_holdings(self, mock_fetch, mock_xml, *_):
        """
        The latest filing and the previous quarter's are each completed before parsing.
        """
        latest = _filing("2025-03-31", "2025-05-15")
        previous = _filing("2024-12-31", "2025-04-09", "NEW HOLDINGS")
        completed = {**previous, "xml_content": b"merged"}
        mock_fetch.return_value = [latest, previous]

        with patch(
            "database.updater.complete_new_holdings",
            side_effect=lambda _cik, f: completed if f is previous else f,
        ) as mock_complete:
            self.assertTrue(process_fund({"CIK": "1", "Fund": "Orion"}))

        completed_inputs = [c.args[1] for c in mock_complete.call_args_list]
        self.assertIn(latest, completed_inputs)
        self.assertIn(previous, completed_inputs)
        self.assertEqual(mock_xml.call_args_list[-1].args[0], b"merged")


if __name__ == "__main__":
    unittest.main()

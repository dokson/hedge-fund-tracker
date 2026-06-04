import unittest
from unittest.mock import patch

from app.stocks.ticker_changes import (
    apply_ticker_changes,
    detect_applicable_ticker_changes,
)

_MODULE = "app.stocks.ticker_changes"


class TestDetectApplicableTickerChanges(unittest.TestCase):
    """
    Tests the detection step: NASDAQ symbol changes filtered down to those whose
    old symbol is actually tracked in stocks.csv.
    """

    @patch(f"{_MODULE}.find_cusips_for_ticker")
    @patch(f"{_MODULE}.Nasdaq")
    def test_returns_only_changes_present_in_stocks(self, mock_nasdaq, mock_find):
        """
        Only NASDAQ changes whose oldSymbol resolves to tracked CUSIPs are
        returned; the total reflects every fetched change.
        """
        mock_nasdaq.get_symbol_changes.return_value = [
            {"oldSymbol": "OLD1", "newSymbol": "NEW1", "companyName": "Co One"},
            {"oldSymbol": "OLD2", "newSymbol": "NEW2", "companyName": "Co Two"},
        ]
        mock_find.side_effect = lambda sym: (
            [{"CUSIP": "C1", "Ticker": "OLD1", "Company": "Co One"}] if sym == "OLD1" else []
        )

        result = detect_applicable_ticker_changes()

        self.assertEqual(result["total_changes"], 2)
        self.assertEqual(len(result["applicable"]), 1)
        self.assertEqual(result["applicable"][0]["oldSymbol"], "OLD1")
        self.assertEqual(result["applicable"][0]["cusips"], ["C1"])

    @patch(f"{_MODULE}.find_cusips_for_ticker", return_value=[])
    @patch(f"{_MODULE}.Nasdaq")
    def test_empty_when_no_matches(self, mock_nasdaq, _mock_find):
        """
        When no fetched change matches a tracked ticker, applicable is empty.
        """
        mock_nasdaq.get_symbol_changes.return_value = [
            {"oldSymbol": "OLD1", "newSymbol": "NEW1", "companyName": "Co One"},
        ]
        result = detect_applicable_ticker_changes()
        self.assertEqual(result["total_changes"], 1)
        self.assertEqual(result["applicable"], [])


class TestApplyTickerChanges(unittest.TestCase):
    """
    Tests the apply step: each applicable change triggers an update_ticker call,
    enriched with the new company name from YFinance when available.
    """

    @patch(f"{_MODULE}.update_ticker")
    @patch(f"{_MODULE}.YFinance")
    @patch(f"{_MODULE}.find_cusips_for_ticker")
    @patch(f"{_MODULE}.Nasdaq")
    def test_applies_matching_change_with_yfinance_company(
        self, mock_nasdaq, mock_find, mock_yf, mock_update
    ):
        """
        A matching change calls update_ticker with the YFinance-resolved company
        and reports it in the applied list.
        """
        mock_nasdaq.get_symbol_changes.return_value = [
            {"oldSymbol": "OLD1", "newSymbol": "NEW1", "companyName": "Stale Co"},
        ]
        mock_find.return_value = [{"CUSIP": "C1", "Ticker": "OLD1", "Company": "Stale Co"}]
        mock_yf.get_company.return_value = "Fresh Co"

        result = apply_ticker_changes()

        mock_update.assert_called_once_with("OLD1", "NEW1", new_company="Fresh Co")
        self.assertEqual(
            result["applied"], [{"old": "OLD1", "new": "NEW1", "companyName": "Fresh Co"}]
        )
        self.assertIn("Applied 1 ticker change", result["message"])

    @patch(f"{_MODULE}.update_ticker")
    @patch(f"{_MODULE}.YFinance")
    @patch(f"{_MODULE}.find_cusips_for_ticker")
    @patch(f"{_MODULE}.Nasdaq")
    def test_falls_back_to_nasdaq_company_when_yfinance_empty(
        self, mock_nasdaq, mock_find, mock_yf, mock_update
    ):
        """
        When YFinance returns no company, the NASDAQ-provided companyName is used.
        """
        mock_nasdaq.get_symbol_changes.return_value = [
            {"oldSymbol": "OLD1", "newSymbol": "NEW1", "companyName": "Nasdaq Co"},
        ]
        mock_find.return_value = [{"CUSIP": "C1", "Ticker": "OLD1", "Company": "x"}]
        mock_yf.get_company.return_value = None

        result = apply_ticker_changes()

        mock_update.assert_called_once_with("OLD1", "NEW1", new_company="Nasdaq Co")
        self.assertEqual(result["applied"][0]["companyName"], "Nasdaq Co")

    @patch(f"{_MODULE}.update_ticker")
    @patch(f"{_MODULE}.YFinance")
    @patch(f"{_MODULE}.find_cusips_for_ticker", return_value=[])
    @patch(f"{_MODULE}.Nasdaq")
    def test_no_matches_reports_none_applied(self, mock_nasdaq, _mock_find, _mock_yf, mock_update):
        """
        With no matching tickers nothing is updated and the message says so.
        """
        mock_nasdaq.get_symbol_changes.return_value = [
            {"oldSymbol": "OLD1", "newSymbol": "NEW1", "companyName": "Co"},
        ]
        result = apply_ticker_changes()

        mock_update.assert_not_called()
        self.assertEqual(result["applied"], [])
        self.assertIn("No applicable ticker changes", result["message"])


if __name__ == "__main__":
    unittest.main()

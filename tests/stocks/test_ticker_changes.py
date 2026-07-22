import unittest
from unittest.mock import patch

import pandas as pd

from app.stocks.ticker_changes import (
    apply_ticker_changes,
    company_names_match,
    detect_applicable_ticker_changes,
    detect_stale_tickers,
)

_MODULE = "app.stocks.ticker_changes"


def _stocks_df(rows: list[tuple[str, str, str]]) -> pd.DataFrame:
    """
    Builds a stocks.csv-shaped DataFrame (indexed by CUSIP) from
    (cusip, ticker, company) tuples.
    """
    df = pd.DataFrame(rows, columns=["CUSIP", "Ticker", "Company"])
    return df.set_index("CUSIP")


@patch(f"{_MODULE}.OpenFIGI")
@patch(f"{_MODULE}.load_stocks")
class TestDetectStaleTickers(unittest.TestCase):
    """
    Tests the full-database reconciliation against OpenFIGI: rows whose CUSIP
    now maps to a different US symbol for the same company are candidates;
    reused CUSIPs (different company) and cosmetic differences are not.
    """

    def test_reports_same_company_with_new_symbol(self, mock_load, mock_figi):
        """
        A CUSIP mapping to a new symbol with a matching company name is a
        candidate carrying both tickers.
        """
        mock_load.return_value = _stocks_df([("C1", "OLD1", "Northwind Maritime Group Ltd")])
        mock_figi.map_cusips.return_value = {
            "C1": {"ticker": "NEW1", "name": "NORTHWIND MARITIME GROUP LTD"}
        }

        result = detect_stale_tickers()

        self.assertEqual(result["checked"], 1)
        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(
            result["candidates"][0],
            {
                "cusip": "C1",
                "oldTicker": "OLD1",
                "newTicker": "NEW1",
                "company": "Northwind Maritime Group Ltd",
                "figiName": "NORTHWIND MARITIME GROUP LTD",
            },
        )

    def test_ignores_reused_cusip_with_different_company(self, mock_load, mock_figi):
        """
        A CUSIP whose FIGI record names an unrelated company is not a
        candidate (identity not confirmed).
        """
        mock_load.return_value = _stocks_df([("C1", "OLD1", "Orbital Rocket Technologies Corp")])
        mock_figi.map_cusips.return_value = {
            "C1": {"ticker": "NEW1", "name": "Thematic New Issue ETF"}
        }

        result = detect_stale_tickers()

        self.assertEqual(result["candidates"], [])

    def test_ignores_cosmetic_symbol_differences(self, mock_load, mock_figi):
        """
        Bond descriptors and share-class separators normalize to the tracked
        symbol and are not candidates.
        """
        mock_load.return_value = _stocks_df(
            [
                ("C1", "TKR", "Northwind Maritime Group Ltd"),
                ("C2", "STEM.A", "Acme Logistics Inc"),
            ]
        )
        mock_figi.map_cusips.return_value = {
            "C1": {"ticker": "TKR 2.5 03/01/27", "name": "NORTHWIND MARITIME GROUP LTD"},
            "C2": {"ticker": "STEM/A", "name": "ACME LOGISTICS INC"},
        }

        result = detect_stale_tickers()

        self.assertEqual(result["candidates"], [])

    def test_ignores_unresolved_cusips(self, mock_load, mock_figi):
        """
        CUSIPs OpenFIGI cannot resolve are counted but never candidates.
        """
        mock_load.return_value = _stocks_df([("C1", "OLD1", "Northwind Maritime Group Ltd")])
        mock_figi.map_cusips.return_value = {}

        result = detect_stale_tickers()

        self.assertEqual(result["checked"], 1)
        self.assertEqual(result["resolved"], 0)
        self.assertEqual(result["candidates"], [])

    def test_ignores_fund_alias_and_warrant_suffix_variants(self, mock_load, mock_figi):
        """
        FIGI's X-wrapped aliases for listed funds and W/WS warrant-suffix
        conventions are the same security, not ticker changes.
        """
        mock_load.return_value = _stocks_df(
            [
                ("C1", "ABC", "Nuveen Example Municipal Fund"),
                ("C2", "DEFWS", "Acme Logistics Inc"),
            ]
        )
        mock_figi.map_cusips.return_value = {
            "C1": {"ticker": "XABCX", "name": "NUVEEN EXAMPLE MUNICIPAL FUND"},
            "C2": {"ticker": "DEFW", "name": "ACME LOGISTICS INC"},
        }

        result = detect_stale_tickers()

        self.assertEqual(result["candidates"], [])


class TestCompanyNamesMatch(unittest.TestCase):
    """
    Tests the company-name similarity guard used to reject ticker collisions:
    a NASDAQ symbol change whose company is unrelated to the tracked one.
    """

    def test_identical_names_match(self):
        """
        The exact same name on both sides matches.
        """
        self.assertTrue(company_names_match("Co One", "Co One"))

    def test_share_class_suffix_matches(self):
        """
        The NASDAQ name with a share-class suffix appended still matches the
        tracked base name.
        """
        self.assertTrue(
            company_names_match(
                "Northwind Maritime Group Ltd",
                "Northwind Maritime Group Ltd Class A Ordinary Shares",
            )
        )

    def test_unrelated_names_do_not_match(self):
        """
        Two unrelated companies that happened to share a ticker do not match.
        """
        self.assertFalse(
            company_names_match("Orbital Rocket Technologies Corp", "Thematic New Issue ETF")
        )

    def test_generic_token_overlap_does_not_match(self):
        """
        Sharing only one distinctive token plus generic suffixes is not enough.
        """
        self.assertFalse(company_names_match("Acme Inc", "Acme Hospitality Trust Inc"))

    def test_empty_name_does_not_match(self):
        """
        A blank name on either side can never be verified, so it never matches.
        """
        self.assertFalse(company_names_match("", "Co One"))
        self.assertFalse(company_names_match("Co One", ""))


@patch(f"{_MODULE}.OpenFIGI")
class TestDetectApplicableTickerChanges(unittest.TestCase):
    """
    Tests the detection step: NASDAQ symbol changes filtered down to those whose
    old symbol is actually tracked in stocks.csv, then verified via OpenFIGI
    (CUSIP identity) with the company-name guard as fallback.

    The class-level OpenFIGI mock is passed as each test's last argument;
    tests configure ``get_ticker`` per scenario (None = FIGI unavailable).
    """

    @patch(f"{_MODULE}.find_cusips_for_ticker")
    @patch(f"{_MODULE}.Nasdaq")
    def test_returns_only_changes_present_in_stocks(self, mock_nasdaq, mock_find, mock_figi):
        """
        Only NASDAQ changes whose oldSymbol resolves to tracked CUSIPs are
        returned; the total reflects every fetched change.
        """
        mock_figi.get_ticker.return_value = None
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
    def test_empty_when_no_matches(self, mock_nasdaq, _mock_find, _mock_figi):
        """
        When no fetched change matches a tracked ticker, applicable is empty.
        """
        mock_nasdaq.get_symbol_changes.return_value = [
            {"oldSymbol": "OLD1", "newSymbol": "NEW1", "companyName": "Co One"},
        ]
        result = detect_applicable_ticker_changes()
        self.assertEqual(result["total_changes"], 1)
        self.assertEqual(result["applicable"], [])

    @patch(f"{_MODULE}.find_cusips_for_ticker")
    @patch(f"{_MODULE}.Nasdaq")
    def test_skips_changes_with_mismatched_company(self, mock_nasdaq, mock_find, mock_figi):
        """
        A ticker collision (NASDAQ change for an unrelated company reusing a
        tracked ticker) is excluded from applicable and reported as skipped:
        OpenFIGI still maps the tracked CUSIP to the old symbol and the
        company names are unrelated.
        """
        mock_figi.get_ticker.return_value = "OLD1"
        mock_nasdaq.get_symbol_changes.return_value = [
            {"oldSymbol": "OLD1", "newSymbol": "NEW1", "companyName": "Thematic New Issue ETF"},
        ]
        mock_find.return_value = [
            {"CUSIP": "C1", "Ticker": "OLD1", "Company": "Orbital Rocket Technologies Corp"}
        ]

        result = detect_applicable_ticker_changes()

        self.assertEqual(result["applicable"], [])
        self.assertEqual(len(result["skipped"]), 1)
        self.assertEqual(result["skipped"][0]["oldSymbol"], "OLD1")
        self.assertEqual(result["skipped"][0]["cusips"], ["C1"])
        self.assertEqual(
            result["skipped"][0]["trackedCompanies"], ["Orbital Rocket Technologies Corp"]
        )
        self.assertIn("company name", result["skipped"][0]["reason"])

    @patch(f"{_MODULE}.find_cusips_for_ticker")
    @patch(f"{_MODULE}.Nasdaq")
    def test_accepts_share_class_suffix_variant(self, mock_nasdaq, mock_find, mock_figi):
        """
        A NASDAQ name that is the tracked company plus share-class boilerplate
        is still applicable when OpenFIGI is unavailable.
        """
        mock_figi.get_ticker.return_value = None
        mock_nasdaq.get_symbol_changes.return_value = [
            {
                "oldSymbol": "OLD1",
                "newSymbol": "NEW1",
                "companyName": "Northwind Maritime Group Ltd Class A Ordinary Shares",
            },
        ]
        mock_find.return_value = [
            {"CUSIP": "C1", "Ticker": "OLD1", "Company": "Northwind Maritime Group Ltd"}
        ]

        result = detect_applicable_ticker_changes()

        self.assertEqual(len(result["applicable"]), 1)
        self.assertEqual(result["skipped"], [])

    @patch(f"{_MODULE}.find_cusips_for_ticker")
    @patch(f"{_MODULE}.Nasdaq")
    def test_figi_confirmation_overrides_name_mismatch(self, mock_nasdaq, mock_find, mock_figi):
        """
        When OpenFIGI maps the tracked CUSIP to the NEW symbol, the change is
        applicable even if the company was renamed (names no longer match).
        """
        mock_figi.get_ticker.return_value = "NEW1"
        mock_nasdaq.get_symbol_changes.return_value = [
            {"oldSymbol": "OLD1", "newSymbol": "NEW1", "companyName": "Rebranded Ventures Inc"},
        ]
        mock_find.return_value = [
            {"CUSIP": "C1", "Ticker": "OLD1", "Company": "Original Legacy Industries Inc"}
        ]

        result = detect_applicable_ticker_changes()

        self.assertEqual(len(result["applicable"]), 1)
        self.assertEqual(result["skipped"], [])

    @patch(f"{_MODULE}.find_cusips_for_ticker")
    @patch(f"{_MODULE}.Nasdaq")
    def test_skips_when_figi_maps_cusip_elsewhere(self, mock_nasdaq, mock_find, mock_figi):
        """
        When OpenFIGI maps the tracked CUSIP to a third, unrelated symbol, the
        change is skipped even if the company names happen to match.
        """
        mock_figi.get_ticker.return_value = "OTHER"
        mock_nasdaq.get_symbol_changes.return_value = [
            {"oldSymbol": "OLD1", "newSymbol": "NEW1", "companyName": "Co One"},
        ]
        mock_find.return_value = [{"CUSIP": "C1", "Ticker": "OLD1", "Company": "Co One"}]

        result = detect_applicable_ticker_changes()

        self.assertEqual(result["applicable"], [])
        self.assertEqual(len(result["skipped"]), 1)
        self.assertIn("OpenFIGI", result["skipped"][0]["reason"])


@patch(f"{_MODULE}.OpenFIGI")
class TestApplyTickerChanges(unittest.TestCase):
    """
    Tests the apply step: each applicable change triggers an update_ticker call,
    enriched with the new company name from YFinance when available.

    The class-level OpenFIGI mock is passed as each test's last argument.
    """

    @patch(f"{_MODULE}.update_ticker")
    @patch(f"{_MODULE}.YFinance")
    @patch(f"{_MODULE}.find_cusips_for_ticker")
    @patch(f"{_MODULE}.Nasdaq")
    def test_applies_matching_change_with_yfinance_company(
        self, mock_nasdaq, mock_find, mock_yf, mock_update, mock_figi
    ):
        """
        A matching change calls update_ticker with the YFinance-resolved company
        and reports it in the applied list.
        """
        mock_figi.get_ticker.return_value = None
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
        self, mock_nasdaq, mock_find, mock_yf, mock_update, mock_figi
    ):
        """
        When YFinance returns no company, the NASDAQ-provided companyName is used.
        """
        mock_figi.get_ticker.return_value = None
        mock_nasdaq.get_symbol_changes.return_value = [
            {"oldSymbol": "OLD1", "newSymbol": "NEW1", "companyName": "Nasdaq Co"},
        ]
        mock_find.return_value = [{"CUSIP": "C1", "Ticker": "OLD1", "Company": "Nasdaq Co"}]
        mock_yf.get_company.return_value = None

        result = apply_ticker_changes()

        mock_update.assert_called_once_with("OLD1", "NEW1", new_company="Nasdaq Co")
        self.assertEqual(result["applied"][0]["companyName"], "Nasdaq Co")

    @patch(f"{_MODULE}.update_ticker")
    @patch(f"{_MODULE}.YFinance")
    @patch(f"{_MODULE}.find_cusips_for_ticker", return_value=[])
    @patch(f"{_MODULE}.Nasdaq")
    def test_no_matches_reports_none_applied(
        self, mock_nasdaq, _mock_find, _mock_yf, mock_update, _mock_figi
    ):
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

    @patch(f"{_MODULE}.update_ticker")
    @patch(f"{_MODULE}.YFinance")
    @patch(f"{_MODULE}.find_cusips_for_ticker")
    @patch(f"{_MODULE}.Nasdaq")
    def test_does_not_apply_mismatched_company(
        self, mock_nasdaq, mock_find, _mock_yf, mock_update, mock_figi
    ):
        """
        A ticker collision is never applied: no update_ticker call, and the
        result reports the change as skipped.
        """
        mock_figi.get_ticker.return_value = "OLD1"
        mock_nasdaq.get_symbol_changes.return_value = [
            {"oldSymbol": "OLD1", "newSymbol": "NEW1", "companyName": "Thematic New Issue ETF"},
        ]
        mock_find.return_value = [
            {"CUSIP": "C1", "Ticker": "OLD1", "Company": "Orbital Rocket Technologies Corp"}
        ]

        result = apply_ticker_changes()

        mock_update.assert_not_called()
        self.assertEqual(result["applied"], [])
        self.assertEqual(len(result["skipped"]), 1)
        self.assertEqual(result["skipped"][0]["oldSymbol"], "OLD1")
        self.assertIn("Skipped 1", result["message"])


if __name__ == "__main__":
    unittest.main()

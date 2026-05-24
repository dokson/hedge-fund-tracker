import unittest
from unittest.mock import patch

import pandas as pd

from app.stocks.classification import resolve_industry


def _stocks_df(rows: list[tuple[str, str, str, str]]) -> pd.DataFrame:
    """
    Builds an in-memory stocks DataFrame indexed by CUSIP, matching what
    load_stocks() returns at runtime.
    """
    df = pd.DataFrame(rows, columns=["CUSIP", "Ticker", "Company", "Industry"])
    return df.set_index("CUSIP")


class TestResolveIndustry(unittest.TestCase):
    """
    resolve_industry runs a three-step fallback chain:
       1. YFinance.get_classification
       2. Same-Company lookup in stocks.csv
       3. Groq LLM classification (when GROQ_API_KEY is set)
    Returns "" when every step misses, so callers can store an empty Industry
    without crashing.
    """

    @patch("app.stocks.classification.YFinance.get_classification")
    @patch("app.stocks.classification.load_stocks")
    def test_returns_yfinance_industry_when_present(self, mock_load, mock_yf):
        """
        Step 1 wins: yfinance.get_classification returns an industry → use it.
        """
        mock_yf.return_value = {"sector": "Technology", "industry": "Software - Application"}
        mock_load.return_value = _stocks_df([])

        self.assertEqual(resolve_industry("AAPL", "Apple Inc"), "Software - Application")
        mock_load.assert_not_called()  # short-circuited at step 1

    @patch("app.stocks.classification._llm_classify")
    @patch("app.stocks.classification.YFinance.get_classification")
    @patch("app.stocks.classification.load_stocks")
    def test_falls_back_to_same_company_industry(self, mock_load, mock_yf, mock_llm):
        """
        Step 2 wins: yfinance misses, but another CUSIP with the SAME Company
        name already has an Industry → inherit it.
        """
        mock_yf.return_value = None
        mock_load.return_value = _stocks_df(
            [
                ("111", "AEVA", "Aeva Technologies Inc", "Software - Infrastructure"),
                ("222", "OTHER", "Other Co", "Banks - Regional"),
            ]
        )

        result = resolve_industry("AEVAW", "Aeva Technologies Inc")

        self.assertEqual(result, "Software - Infrastructure")
        mock_llm.assert_not_called()  # short-circuited at step 2

    @patch("app.stocks.classification._llm_classify")
    @patch("app.stocks.classification.YFinance.get_classification")
    @patch("app.stocks.classification.load_stocks")
    def test_falls_back_to_llm_when_name_unknown(self, mock_load, mock_yf, mock_llm):
        """
        Step 3 wins: yfinance miss, no matching Company in DB, LLM picks an
        industry from the closed vocabulary.
        """
        mock_yf.return_value = None
        mock_load.return_value = _stocks_df([])
        mock_llm.return_value = "Banks - Regional"

        result = resolve_industry("BANK", "Fiinu Plc")

        self.assertEqual(result, "Banks - Regional")
        mock_llm.assert_called_once_with("BANK", "Fiinu Plc")

    @patch("app.stocks.classification._llm_classify")
    @patch("app.stocks.classification.YFinance.get_classification")
    @patch("app.stocks.classification.load_stocks")
    def test_returns_empty_when_every_fallback_misses(self, mock_load, mock_yf, mock_llm):
        """
        All three steps return nothing → resolve_industry returns "" so the row
        is still persistable with an empty Industry the AI backfill can revisit.
        """
        mock_yf.return_value = None
        mock_load.return_value = _stocks_df([])
        mock_llm.return_value = None

        self.assertEqual(resolve_industry("XYZ", "Unknown Co"), "")

    @patch("app.stocks.classification._llm_classify")
    @patch("app.stocks.classification.YFinance.get_classification")
    @patch("app.stocks.classification.load_stocks")
    def test_ignores_empty_industry_rows_when_matching_by_name(self, mock_load, mock_yf, mock_llm):
        """
        A same-Company row with EMPTY Industry should NOT short-circuit the
        chain — we keep searching (and ultimately reach the LLM step).
        """
        mock_yf.return_value = None
        mock_load.return_value = _stocks_df(
            [("111", "OLDX", "Aeva Technologies Inc", "")],  # empty Industry
        )
        mock_llm.return_value = "Auto Parts"

        result = resolve_industry("AEVAW", "Aeva Technologies Inc")

        self.assertEqual(result, "Auto Parts")
        mock_llm.assert_called_once()

    @patch("app.stocks.classification.YFinance.get_classification")
    @patch("app.stocks.classification.load_stocks")
    def test_empty_company_skips_name_match(self, mock_load, mock_yf):
        """
        When Company is empty, skip the same-name lookup entirely (would match
        every empty-name row in the DB otherwise).
        """
        mock_yf.return_value = None
        mock_load.return_value = _stocks_df([("111", "AEVA", "", "Software - Infrastructure")])
        # Without a Company we cannot rely on the name match — the chain falls
        # straight through to whatever the LLM step returns (here mocked None
        # implicitly because no LLM patch is in scope → real call would happen;
        # we assert only that name match did not return the wrong value).
        with patch("app.stocks.classification._llm_classify", return_value=None):
            self.assertEqual(resolve_industry("AEVAW", ""), "")


if __name__ == "__main__":
    unittest.main()

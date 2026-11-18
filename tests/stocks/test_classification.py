import unittest
from unittest.mock import patch

import pandas as pd

from app.ai.clients.groq_client import GroqClient
from app.stocks.classification import (
    GEMINI_CLASSIFIER_MODEL,
    _llm_classify,
    _looks_like_blank_check,
    resolve_industry,
)


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
       1. Same issuer in stocks.csv (same Company name, else agreeing CUSIP issuer code)
       2. YFinance.get_classification
       3. LLM classification (Gemini flash-lite, Groq fallback)
    Returns "" when every step misses, so callers can store an empty Industry
    without crashing.
    """

    @patch("app.stocks.classification.YFinance.get_classification")
    @patch("app.stocks.classification.load_stocks")
    def test_returns_yfinance_industry_when_issuer_unknown(self, mock_load, mock_yf):
        """
        No stored row for the issuer → yfinance.get_classification decides.
        """
        mock_yf.return_value = {"sector": "Technology", "industry": "Software - Application"}
        mock_load.return_value = _stocks_df([])

        self.assertEqual(resolve_industry("AAPL", "Apple Inc"), "Software - Application")

    @patch("app.stocks.classification._llm_classify")
    @patch("app.stocks.classification.YFinance.get_classification")
    @patch("app.stocks.classification.load_stocks")
    def test_stored_same_company_industry_wins_over_yfinance(self, mock_load, mock_yf, mock_llm):
        """
        A new share class inherits the Industry its issuer already carries even
        when Yahoo now classifies it differently, so one Company never maps to
        two industries (QVCG came back 'Specialty Retail' beside 'Internet Retail').
        """
        mock_yf.return_value = {"sector": "Consumer Cyclical", "industry": "Specialty Retail"}
        mock_load.return_value = _stocks_df(
            [
                ("74915M100", "QVCGA", "QVC Group Inc", "Internet Retail"),
                ("222", "OTHER", "Other Co", "Banks - Regional"),
            ]
        )

        result = resolve_industry("QVCG", "QVC Group Inc", "74915M407")

        self.assertEqual(result, "Internet Retail")
        mock_llm.assert_not_called()

    @patch("app.stocks.classification._llm_classify")
    @patch("app.stocks.classification.YFinance.get_classification")
    @patch("app.stocks.classification.load_stocks")
    def test_issuer_code_match_covers_a_differently_named_warrant(
        self, mock_load, mock_yf, mock_llm
    ):
        """
        A warrant filed under another spelling of the issuer's name still shares
        the CUSIP issuer code (first 6 characters) with the classified stock.
        """
        mock_yf.return_value = None
        mock_llm.return_value = None
        mock_load.return_value = _stocks_df(
            [("462921107", "IQMX", "Iqm Quantum Computers Oy-Adr", "Computer Hardware")]
        )

        result = resolve_industry("IQMXW", "IQM Quantum Computers Oyj", "462921115")

        self.assertEqual(result, "Computer Hardware")

    @patch("app.stocks.classification._llm_classify")
    @patch("app.stocks.classification.YFinance.get_classification")
    @patch("app.stocks.classification.load_stocks")
    def test_disagreeing_issuer_code_siblings_are_not_trusted(self, mock_load, mock_yf, mock_llm):
        """
        When the rows sharing the issuer code disagree, none is picked: the
        chain falls through to the providers.
        """
        mock_yf.return_value = {"sector": "Technology", "industry": "Software - Application"}
        mock_load.return_value = _stocks_df(
            [
                ("123456101", "AAA", "Alpha Inc", "Banks - Regional"),
                ("123456200", "AAB", "Alpha Holdings", "Auto Parts"),
            ]
        )

        result = resolve_industry("AABW", "Alpha Warrants", "123456119")

        self.assertEqual(result, "Software - Application")
        mock_llm.assert_not_called()

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


_VOCAB = ["Banks - Regional", "Shell Companies", "Software - Application"]


def _hierarchy() -> pd.DataFrame:
    """
    Builds a small sector hierarchy covering the placeholder vocabulary.
    """
    return pd.DataFrame(
        {"Sector": ["Financial Services", "Financial Services", "Technology"], "Industry": _VOCAB}
    )


class TestLlmClassify(unittest.TestCase):
    """
    _llm_classify asks Gemini flash-lite first with a vocabulary-constrained schema
    and falls back to Groq when Gemini is unavailable or answers badly.
    """

    def _run(
        self,
        company: str = "Example Holdings Inc",
        gemini: object = '{"industry": "Banks - Regional"}',
        groq: object = '{"industry": "Software - Application"}',
        env: dict | None = None,
    ):
        """
        Runs _llm_classify with both clients mocked; returns (result, gemini_cls, groq_cls).
        """
        env = {"GOOGLE_API_KEY": "g-key", "GROQ_API_KEY": "q-key"} if env is None else env
        with (
            patch.dict("os.environ", env, clear=True),
            patch("app.stocks.classification.load_sector_hierarchy", return_value=_hierarchy()),
            patch("app.stocks.classification.GoogleAIClient") as gemini_cls,
            patch("app.stocks.classification.GroqClient") as groq_cls,
        ):
            gemini_call = gemini_cls.return_value.generate_content
            groq_call = groq_cls.return_value.generate_content
            for call, value in ((gemini_call, gemini), (groq_call, groq)):
                if isinstance(value, (BaseException, list)):
                    call.side_effect = value
                else:
                    call.return_value = value
            result = _llm_classify("XYZ", company)
        return result, gemini_cls, groq_cls

    def test_gemini_called_first_with_constrained_schema_and_low_reasoning(self):
        """
        Gemini flash-lite is asked with an enum schema over the sorted vocabulary.
        """
        result, gemini_cls, groq_cls = self._run()
        self.assertEqual(result, "Banks - Regional")
        self.assertEqual(gemini_cls.call_args.kwargs["model"], GEMINI_CLASSIFIER_MODEL)
        self.assertEqual(gemini_cls.call_args.kwargs["api_key"], "g-key")
        kwargs = gemini_cls.return_value.generate_content.call_args.kwargs
        self.assertEqual(kwargs["reasoning"], "low")
        schema = kwargs["response_schema"]
        self.assertEqual(schema["properties"]["industry"]["enum"], sorted(_VOCAB))
        self.assertEqual(schema["required"], ["industry"])
        self.assertFalse(schema["additionalProperties"])
        groq_cls.assert_not_called()

    def test_gemini_drops_enum_above_its_size_limit(self):
        """
        Gemini rejects large enums with a bare 400, so an oversized vocabulary is
        sent as a plain string and validated in code; Groq keeps the enum.
        """
        with patch("app.stocks.classification.GEMINI_MAX_ENUM", 2):
            result, gemini_cls, _ = self._run()
            _, _, groq_cls = self._run(env={"GROQ_API_KEY": "q-key"})
        self.assertEqual(result, "Banks - Regional")
        gemini_schema = gemini_cls.return_value.generate_content.call_args.kwargs["response_schema"]
        self.assertEqual(gemini_schema["properties"]["industry"], {"type": "string"})
        groq_schema = groq_cls.return_value.generate_content.call_args.kwargs["response_schema"]
        self.assertEqual(groq_schema["properties"]["industry"]["enum"], sorted(_VOCAB))

    def test_missing_google_key_uses_groq(self):
        """
        Without GOOGLE_API_KEY, Gemini is skipped and Groq answers.
        """
        result, gemini_cls, groq_cls = self._run(env={"GROQ_API_KEY": "q-key"})
        self.assertEqual(result, "Software - Application")
        gemini_cls.assert_not_called()
        self.assertEqual(groq_cls.call_args.kwargs["model"], GroqClient.DEFAULT_MODEL)
        kwargs = groq_cls.return_value.generate_content.call_args.kwargs
        self.assertEqual(kwargs["reasoning"], "low")
        self.assertIn("enum", kwargs["response_schema"]["properties"]["industry"])

    def test_gemini_error_uses_groq(self):
        """
        A Gemini exception falls back to Groq.
        """
        result, _, groq_cls = self._run(gemini=RuntimeError("boom"))
        self.assertEqual(result, "Software - Application")
        groq_cls.assert_called_once()

    def test_non_vocabulary_answer_falls_back(self):
        """
        An answer outside the vocabulary (or unparseable) is not trusted.
        """
        result, _, _ = self._run(gemini='{"industry": "Made Up Industry"}')
        self.assertEqual(result, "Software - Application")
        result, _, _ = self._run(gemini="not json")
        self.assertEqual(result, "Software - Application")

    def test_both_fail_returns_none(self):
        """
        Both providers failing yields None.
        """
        result, _, _ = self._run(gemini=RuntimeError("x"), groq='{"industry": "Nope"}')
        self.assertIsNone(result)

    def test_no_keys_returns_none(self):
        """
        With no API keys at all, no client is built and None is returned.
        """
        result, gemini_cls, groq_cls = self._run(env={})
        self.assertIsNone(result)
        gemini_cls.assert_not_called()
        groq_cls.assert_not_called()

    def test_shell_accepted_for_blank_check_name(self):
        """
        Shell Companies is kept when the name looks like a blank-check vehicle.
        """
        result, _, groq_cls = self._run(
            company="Example Acquisition Corp", gemini='{"industry": "Shell Companies"}'
        )
        self.assertEqual(result, "Shell Companies")
        groq_cls.assert_not_called()

    def test_shell_rejected_for_ordinary_name(self):
        """
        Shell Companies on an ordinary name triggers one re-ask without that label.
        """
        shell = '{"industry": "Shell Companies"}'
        result, gemini_cls, groq_cls = self._run(
            company="Example Robotics Inc",
            gemini=[shell, '{"industry": "Software - Application"}'],
        )
        self.assertEqual(result, "Software - Application")
        groq_cls.assert_not_called()
        calls = gemini_cls.return_value.generate_content.call_args_list
        self.assertEqual(len(calls), 2)
        retry_enum = calls[1].kwargs["response_schema"]["properties"]["industry"]["enum"]
        self.assertNotIn("Shell Companies", retry_enum)
        self.assertEqual(retry_enum, ["Banks - Regional", "Software - Application"])
        self.assertIn("has an operating business", calls[1].args[0])
        self.assertNotIn("- Shell Companies", calls[1].args[0])


class TestLooksLikeBlankCheck(unittest.TestCase):
    """
    The blank-check name pattern is deliberately narrow.
    """

    def test_patterns(self):
        """
        Blank-check wording matches; ordinary names do not.
        """
        for name in (
            "Example Acquisition Corp",
            "Sample Merger Corp II",
            "Placeholder Blank Check Co",
            "Demo SPAC Inc",
        ):
            self.assertTrue(_looks_like_blank_check(name), name)
        for name in ("Example Robotics Inc", "Sample Acquisitions Bank", ""):
            self.assertFalse(_looks_like_blank_check(name), name)


if __name__ == "__main__":
    unittest.main()

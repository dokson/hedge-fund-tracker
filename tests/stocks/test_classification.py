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
       1. YFinance.get_classification
       2. Same-Company lookup in stocks.csv
       3. LLM classification (Gemini flash-lite, Groq fallback)
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
        self.assertEqual(GEMINI_CLASSIFIER_MODEL, "gemini-3.5-flash-lite")
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

    def test_prompt_wording_for_warrants_and_spacs(self):
        """
        Warrants/rights/units take the issuer's industry; Shell Companies is SPAC-only.
        """
        _, gemini_cls, _ = self._run()
        prompt = gemini_cls.return_value.generate_content.call_args.args[0]
        self.assertIn("warrants, rights and units take the issuer's operating industry", prompt)
        self.assertIn("blank-check/SPAC company that has not yet completed a merger", prompt)
        self.assertNotIn("warrant, unit, SPAC pre-merger or other special structure", prompt)

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

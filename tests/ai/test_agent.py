import unittest
from unittest.mock import MagicMock, patch

import pandas as pd
from tenacity import RetryError

from app.ai.agent import AnalystAgent


def _make_stock_df(**kwargs):
    """
    Builds a minimal stock DataFrame for due diligence tests, with optional overrides.
    """
    defaults = {
        "Ticker": ["AAPL"],
        "Company": ["Apple Inc"],
        "Value": [1_000_000],
        "Delta_Value": [50_000],
        "Delta": ["NEW"],
    }
    defaults.update(kwargs)
    return pd.DataFrame(defaults)


def _make_analysis_df():
    """
    Builds a minimal analysis DataFrame with two numeric metrics for Promise Score tests.
    """
    return pd.DataFrame(
        {
            "Ticker": ["AAPL", "MSFT", "GOOGL"],
            "Metric1": [10, 20, 15],
            "Metric2": [2, 5, 3],
        }
    )


class TestAnalystAgentInit(unittest.TestCase):
    @patch("app.ai.agent.quarter_analysis")
    @patch("app.ai.agent.get_quarter_date")
    def test_stores_quarter_string(self, mock_date, mock_analysis):
        """
        Stores the quarter string as an instance attribute.
        """
        mock_date.return_value = "2023-12-31"
        mock_analysis.return_value = pd.DataFrame()

        agent = AnalystAgent("2023Q4")

        self.assertEqual(agent.quarter, "2023Q4")

    @patch("app.ai.agent.quarter_analysis")
    @patch("app.ai.agent.get_quarter_date")
    def test_stores_filing_date_from_quarter(self, mock_date, mock_analysis):
        """
        Converts the quarter string to a filing date via get_quarter_date().
        """
        mock_date.return_value = "2023-12-31"
        mock_analysis.return_value = pd.DataFrame()

        agent = AnalystAgent("2023Q4")

        self.assertEqual(agent.filing_date, "2023-12-31")

    @patch("app.ai.agent.quarter_analysis")
    @patch("app.ai.agent.get_quarter_date")
    def test_stores_provided_ai_client(self, mock_date, mock_analysis):
        """
        Stores the provided AI client as an instance attribute.
        """
        mock_date.return_value = "2023-12-31"
        mock_analysis.return_value = pd.DataFrame()
        mock_client = MagicMock()

        agent = AnalystAgent("2023Q4", ai_client=mock_client)

        self.assertEqual(agent.ai_client, mock_client)

    @patch("app.ai.agent.quarter_analysis")
    @patch("app.ai.agent.get_quarter_date")
    def test_loads_analysis_dataframe_on_init(self, mock_date, mock_analysis):
        """
        Loads the quarter analysis DataFrame by calling quarter_analysis() on init.
        """
        mock_date.return_value = "2023-12-31"
        expected_df = _make_analysis_df()
        mock_analysis.return_value = expected_df

        agent = AnalystAgent("2023Q4")

        mock_analysis.assert_called_once_with("2023Q4")
        pd.testing.assert_frame_equal(agent.analysis_df, expected_df)


class TestCalculatePromiseScores(unittest.TestCase):
    """
    Tests for AnalystAgent._calculate_promise_scores().
    This is pure logic with no I/O - no mocks required.
    """

    def setUp(self):
        """
        Patches quarter_analysis and get_quarter_date for AnalystAgent instantiation.

        addCleanup runs even if setUp raises mid-way, so no patcher can leak
        into subsequent tests if a future patcher addition fails.
        """
        q_analysis_patcher = patch("app.ai.agent.quarter_analysis", return_value=pd.DataFrame())
        date_patcher = patch("app.ai.agent.get_quarter_date", return_value="2023-12-31")
        self.addCleanup(q_analysis_patcher.stop)
        self.addCleanup(date_patcher.stop)
        q_analysis_patcher.start()
        date_patcher.start()
        self.mock_ai_client = MagicMock()
        self.agent = AnalystAgent("2023Q4", ai_client=self.mock_ai_client)

    def test_adds_promise_score_column(self):
        """
        Adds a 'Promise_Score' column to the returned DataFrame.
        """
        df = _make_analysis_df()

        result = self.agent._calculate_promise_scores(df, {"Metric1": 0.5, "Metric2": 0.5})

        self.assertIn("Promise_Score", result.columns)

    def test_does_not_mutate_input_dataframe(self):
        """
        Returns a new DataFrame and leaves the original unchanged.
        """
        df = _make_analysis_df()

        self.agent._calculate_promise_scores(df, {"Metric1": 1.0})

        self.assertNotIn("Promise_Score", df.columns)

    def test_scores_are_between_0_and_100(self):
        """
        All Promise_Score values are in the [0, 100] range.
        """
        df = _make_analysis_df()

        result = self.agent._calculate_promise_scores(df, {"Metric1": 0.6, "Metric2": 0.4})

        self.assertTrue((result["Promise_Score"] >= 0).all())
        self.assertTrue((result["Promise_Score"] <= 100).all())

    def test_higher_metric_yields_higher_score(self):
        """
        A row with a higher metric value receives a higher Promise_Score.
        """
        df = pd.DataFrame({"Ticker": ["LOW", "HIGH"], "Metric1": [10, 100]})

        result = self.agent._calculate_promise_scores(df, {"Metric1": 1.0})

        high_score = result.loc[result["Ticker"] == "HIGH", "Promise_Score"].iloc[0]
        low_score = result.loc[result["Ticker"] == "LOW", "Promise_Score"].iloc[0]
        self.assertGreater(high_score, low_score)

    def test_silently_skips_missing_metric_columns(self):
        """
        Does not raise when a weight key is not present in the DataFrame; skips that metric.
        """
        df = _make_analysis_df()

        result = self.agent._calculate_promise_scores(df, {"Metric1": 0.5, "NonExistent": 0.5})

        self.assertIn("Promise_Score", result.columns)

    def test_scaling_weights_by_a_constant_leaves_scores_unchanged(self):
        """
        Only the ratios between weights matter once they are normalized.
        """
        df = _make_analysis_df()
        weights = {"Metric1": 0.6, "Metric2": -0.4}

        base = self.agent._calculate_promise_scores(df, weights)["Promise_Score"]
        scaled = self.agent._calculate_promise_scores(df, {k: v * 7.5 for k, v in weights.items()})[
            "Promise_Score"
        ]

        pd.testing.assert_series_equal(base, scaled)

    def test_best_stock_scores_100_and_worst_0_with_mixed_signs(self):
        """
        Top of every positive metric and bottom of every negative one maps to exactly 100.
        """
        df = pd.DataFrame(
            {
                "Ticker": ["BEST", "MID", "WORST"],
                "Good": [30, 20, 10],
                "Bad": [0, 5, 9],
            }
        )

        result = self.agent._calculate_promise_scores(df, {"Good": 2.0, "Bad": -1.0})
        scores = dict(zip(result["Ticker"], result["Promise_Score"], strict=True))

        self.assertAlmostEqual(scores["BEST"], 100.0)
        self.assertAlmostEqual(scores["WORST"], 0.0)
        self.assertTrue(0 <= scores["MID"] <= 100)

    def test_ordering_matches_the_legacy_percentile_implementation(self):
        """
        Without ties or NaN the new rank mapping is affine in the old one, so ordering is kept.
        """
        df = pd.DataFrame(
            {
                "Ticker": list("ABCDE"),
                "M1": [5, 1, 4, 2, 3],
                "M2": [10, 30, 20, 50, 40],
                "M3": [7, 9, 8, 6, 5],
            }
        )
        weights = {"M1": 0.5, "M2": 0.3, "M3": -0.2}
        legacy = pd.concat([df[m].rank(pct=True) * w for m, w in weights.items()], axis=1).sum(
            axis=1
        )

        result = self.agent._calculate_promise_scores(df, weights)

        self.assertEqual(
            list(result["Promise_Score"].sort_values().index), list(legacy.sort_values().index)
        )

    def test_missing_metric_renormalizes_so_the_max_is_still_100(self):
        """
        Skipping an absent metric must not cap the top score below 100.
        """
        df = _make_analysis_df()

        result = self.agent._calculate_promise_scores(df, {"Metric1": 0.5, "NonExistent": 0.5})

        self.assertAlmostEqual(result["Promise_Score"].max(), 100.0)

    def test_raises_value_error_when_no_metric_is_present(self):
        """
        There is nothing to score on, which is not a retryable AI answer.
        """
        with self.assertRaises(ValueError):
            self.agent._calculate_promise_scores(_make_analysis_df(), {"Nope": 1.0})

    def test_nan_metric_value_still_yields_a_finite_neutral_rank(self):
        """
        A NaN value ranks as 0.5 so the stock keeps a finite score.
        """
        df = pd.DataFrame({"Ticker": ["A", "B", "C"], "M1": [1.0, None, 3.0]})

        result = self.agent._calculate_promise_scores(df, {"M1": 1.0})

        self.assertTrue(result["Promise_Score"].notna().all())
        self.assertAlmostEqual(float(result["Promise_Score"].iloc[1]), 50.0)

    def test_zero_inflated_count_gives_zero_rank_to_the_zeros(self):
        """
        Ties at the minimum share the minimum rank instead of an averaged one.
        """
        df = pd.DataFrame({"Ticker": list("ABCD"), "Count": [0, 0, 0, 4]})

        result = self.agent._calculate_promise_scores(df, {"Count": 1.0})

        self.assertEqual(list(result["Count_rank"]), [0.0, 0.0, 0.0, 1.0])

    def test_constant_column_is_excluded_from_the_score(self):
        """
        A constant column carries no cross-sectional information and is dropped.
        """
        df = pd.DataFrame({"Ticker": list("ABC"), "Flat": [2, 2, 2], "M1": [1, 2, 3]})

        result = self.agent._calculate_promise_scores(df, {"Flat": 0.9, "M1": 0.1})

        self.assertEqual(list(result["Promise_Score"]), [0.0, 50.0, 100.0])
        self.assertEqual(list(result["Flat_rank"]), [0.5, 0.5, 0.5])

    def test_single_stock_gets_a_neutral_score(self):
        """
        With one stock every column is constant, so the score is the neutral 50.
        """
        df = pd.DataFrame({"Ticker": ["A"], "M1": [3]})

        result = self.agent._calculate_promise_scores(df, {"M1": 1.0})

        self.assertAlmostEqual(float(result["Promise_Score"].iloc[0]), 50.0)


def _six_weights(**overrides: object) -> dict:
    """
    Builds a valid six-metric weight set from real metric names, with optional overrides.
    """
    weights: dict = {
        "High_Conviction_Count": 0.2,
        "Max_Portfolio_Pct": 0.2,
        "Ownership_Delta_Avg": 0.2,
        "Net_Buyers": 0.2,
        "Total_Delta_Value": 0.1,
        "New_Holder_Count": 0.1,
    }
    weights.update(overrides)
    return weights


class TestGetPromiseScoreWeights(unittest.TestCase):
    def setUp(self):
        """
        Patches time.sleep, the prompt and the parser, and builds an AnalystAgent.
        """
        for patcher in (
            patch("time.sleep"),
            patch("app.ai.agent.quarter_analysis", return_value=pd.DataFrame()),
            patch("app.ai.agent.get_quarter_date", return_value="2023-12-31"),
            patch("app.ai.agent.promise_score_weights_prompt"),
        ):
            self.addCleanup(patcher.stop)
            patcher.start()
        parse_patcher = patch("app.ai.agent.ResponseParser.extract_and_decode_toon")
        self.addCleanup(parse_patcher.stop)
        self.mock_parse = parse_patcher.start()
        self.mock_ai_client = MagicMock()
        self.mock_ai_client.generate_content.return_value = "mock_response"
        self.agent = AnalystAgent("2023Q4", ai_client=self.mock_ai_client)

    def test_returns_weights_on_valid_response(self):
        """
        Returns the parsed weights dict when the AI response is valid.
        """
        self.mock_parse.return_value = _six_weights()

        self.assertEqual(self.agent._get_promise_score_weights(), _six_weights())

    def test_accepts_weights_whose_sum_is_not_one(self):
        """
        The sum no longer matters: totals of 0.8, 1.1 and 3.0 are all accepted.
        """
        for total in (0.8, 1.1, 3.0):
            weights = {k: v * total for k, v in _six_weights().items()}
            self.mock_parse.return_value = weights

            self.assertEqual(self.agent._get_promise_score_weights(), weights)

    def test_raises_when_metrics_unrecognized(self):
        """
        Any metric key outside the recognized set triggers a retry.
        """
        self.mock_parse.return_value = _six_weights(UnknownMetric=1.0)

        with self.assertRaises(RetryError):
            self.agent._get_promise_score_weights()

    def test_coerces_string_numeric_weights_to_float(self):
        """
        String values that look like numbers are coerced to float.
        """
        self.mock_parse.return_value = _six_weights(High_Conviction_Count="0.2")

        result = self.agent._get_promise_score_weights()

        self.assertEqual(result["High_Conviction_Count"], 0.2)
        for v in result.values():
            self.assertIsInstance(v, float)

    def test_wrongly_signed_weights_trigger_retry(self):
        """
        A positive Seller_Count weight would reward institutional selling.
        """
        self.mock_parse.return_value = _six_weights(Seller_Count=0.6)

        with self.assertRaises(RetryError):
            self.agent._get_promise_score_weights()

    def test_zero_weight_triggers_retry(self):
        """
        A zero weight means the metric should have been omitted.
        """
        self.mock_parse.return_value = _six_weights(Net_Buyers=0.0)

        with self.assertRaises(RetryError):
            self.agent._get_promise_score_weights()

    def test_non_finite_weights_trigger_retry(self):
        """
        NaN or infinite weights would poison normalization.
        """
        for bad in (float("nan"), float("inf")):
            self.mock_parse.return_value = _six_weights(Net_Buyers=bad)

            with self.assertRaises(RetryError):
                self.agent._get_promise_score_weights()

    def test_only_negative_weights_trigger_retry(self):
        """
        Without a positive weight the score can only penalize selling.
        """
        self.mock_parse.return_value = {"Seller_Count": -1.0, "Close_Count": -0.5}
        with (
            patch("app.ai.agent.PromiseScoreValidator.validate_metric_count", return_value=""),
            self.assertRaises(RetryError),
        ):
            self.agent._get_promise_score_weights()

    def test_raises_on_non_numeric_weight(self):
        """
        A value that cannot be coerced to float triggers a retry instead of a TypeError.
        """
        self.mock_parse.return_value = _six_weights(Net_Buyers="0.30Max_Portfolio_Pct")

        with self.assertRaises(RetryError):
            self.agent._get_promise_score_weights()

    def test_too_few_metrics_trigger_retry(self):
        """
        A sparse weight set concentrates the ranking on one axis.
        """
        self.mock_parse.return_value = {"Net_Buyers": 0.5, "Holder_Count": 0.5}

        with self.assertRaises(RetryError):
            self.agent._get_promise_score_weights()

    def test_too_many_metrics_trigger_retry(self):
        """
        More metrics than the maximum spreads weight over correlated breadth signals.
        """
        metrics = [
            "Total_Value",
            "Total_Delta_Value",
            "Max_Portfolio_Pct",
            "Buyer_Count",
            "Seller_Count",
            "Holder_Count",
            "New_Holder_Count",
            "Net_Buyers",
            "Close_Count",
            "Delta",
            "Buyer_Seller_Ratio",
        ]
        self.mock_parse.return_value = {
            m: (-0.05 if m in ("Seller_Count", "Close_Count") else 0.05) for m in metrics
        }

        with self.assertRaises(RetryError):
            self.agent._get_promise_score_weights()


class TestGenerateScoredListScoringFailure(unittest.TestCase):
    def test_returns_empty_frame_when_no_weighted_metric_is_present(self):
        """
        A scoring ValueError is logged and yields an empty DataFrame, like the weights failure.
        """
        with (
            patch("app.ai.agent.quarter_analysis", return_value=_make_analysis_df()),
            patch("app.ai.agent.get_quarter_date", return_value="2023-12-31"),
        ):
            agent = AnalystAgent("2023Q4", ai_client=MagicMock())
        with (
            patch.object(agent, "_get_promise_score_weights", return_value={"Nope": 1.0}),
            patch("app.ai.agent.logger") as mock_logger,
        ):
            result = agent.generate_scored_list(5)

        self.assertTrue(result.empty)
        mock_logger.error.assert_called_once()


class TestComputeAutonomousScores(unittest.TestCase):
    def setUp(self):
        """
        Initializes AnalystAgent with mocked quarter analysis and filing date.
        """
        for patcher in (
            patch("app.ai.agent.quarter_analysis", return_value=pd.DataFrame()),
            patch("app.ai.agent.get_quarter_date", return_value="2023-12-31"),
        ):
            self.addCleanup(patcher.stop)
            patcher.start()
        self.agent = AnalystAgent("2023Q4", ai_client=MagicMock())

    @patch("app.ai.agent.PriceFetcher.get_avg_price", return_value=None)
    @patch("app.ai.agent.YFinance.get_stocks_info")
    def test_prefers_the_yfinance_industry(self, mock_info, mock_avg_price):
        """
        The prompt asks the LLM to refine a sector into an industry, so the
        industry is handed over whenever YFinance has one.
        """
        mock_info.return_value = {
            "AAPL": {"price": 150.0, "sector": "Technology", "industry": "Consumer Electronics"}
        }

        result = self.agent._compute_autonomous_scores(["AAPL"])

        self.assertEqual(result["AAPL"]["Industry"], "Consumer Electronics")

    @patch("app.ai.agent.PriceFetcher.get_avg_price", return_value=None)
    @patch("app.ai.agent.YFinance.get_stocks_info")
    def test_falls_back_to_the_sector(self, mock_info, mock_avg_price):
        """
        Falls back to the sector when YFinance reports no industry.
        """
        mock_info.return_value = {"AAPL": {"price": 150.0, "sector": "Technology"}}

        result = self.agent._compute_autonomous_scores(["AAPL"])

        self.assertEqual(result["AAPL"]["Industry"], "Technology")

    @patch("app.ai.agent.PriceFetcher.get_avg_price", return_value=None)
    @patch("app.ai.agent.YFinance.get_stocks_info", return_value={})
    def test_reports_na_when_neither_is_known(self, mock_info, mock_avg_price):
        """
        Reports "N/A" when YFinance returns nothing for the ticker.
        """
        result = self.agent._compute_autonomous_scores(["AAPL"])

        self.assertEqual(result["AAPL"]["Industry"], "N/A")


class TestGetAIScores(unittest.TestCase):
    def setUp(self):
        """
        Patches time.sleep and initializes AnalystAgent with mocked dependencies.
        """
        # Patch time.sleep to speed up tenacity retries (wait_fixed(1) would add ~4s per test)
        for patcher in (
            patch("time.sleep"),
            patch("app.ai.agent.quarter_analysis", return_value=pd.DataFrame()),
            patch("app.ai.agent.get_quarter_date", return_value="2023-12-31"),
        ):
            self.addCleanup(patcher.stop)
            patcher.start()
        self.mock_ai_client = MagicMock()
        self.agent = AnalystAgent("2023Q4", ai_client=self.mock_ai_client)

    @patch("app.ai.agent.encode")
    @patch("app.ai.agent.ResponseParser.extract_and_decode_toon")
    @patch("app.ai.agent.quantitative_scores_prompt")
    def test_returns_parsed_scores_on_valid_response(self, mock_prompt, mock_parse, mock_encode):
        """
        Returns the AI-parsed score dict when the response contains all required keys.
        """
        valid_scores = {
            "AAPL": {"momentum_score": 80, "low_volatility_score": 60, "risk_score": 40}
        }
        self.mock_ai_client.generate_content.return_value = "mock_response"
        mock_parse.return_value = valid_scores

        result = self.agent._get_ai_scores([{"ticker": "AAPL", "company": "Apple"}])

        self.assertEqual(result, valid_scores)

    @patch("app.ai.agent.encode")
    @patch("app.ai.agent.ResponseParser.extract_and_decode_toon")
    @patch("app.ai.agent.quantitative_scores_prompt")
    def test_scalar_entries_trigger_retry_not_typeerror(self, mock_prompt, mock_parse, mock_encode):
        """
        A flat `TICKER: score` response decodes to scalar values; that must be
        treated as an invalid response (retried) — not escape as a TypeError.
        """
        self.mock_ai_client.generate_content.return_value = "mock_response"
        mock_parse.return_value = {"AAPL": 95}

        with self.assertRaises(RetryError):
            self.agent._get_ai_scores([{"ticker": "AAPL", "company": "Apple"}])

    @patch("app.ai.agent.encode")
    @patch("app.ai.agent.ResponseParser.extract_and_decode_toon")
    @patch("app.ai.agent.quantitative_scores_prompt")
    def test_missing_tickers_trigger_retry(self, mock_prompt, mock_parse, mock_encode):
        """
        A truncated response covering only part of the requested universe must
        not pass validation: missing tickers would silently score 0 downstream.
        """
        self.mock_ai_client.generate_content.return_value = "mock_response"
        mock_parse.return_value = {
            "AAPL": {"momentum_score": 80, "low_volatility_score": 60, "risk_score": 40}
        }

        with self.assertRaises(RetryError):
            self.agent._get_ai_scores(
                [{"ticker": "AAPL", "company": "Apple"}, {"ticker": "MSFT", "company": "Microsoft"}]
            )

    @patch("app.ai.agent.encode")
    @patch("app.ai.agent.ResponseParser.extract_and_decode_toon")
    @patch("app.ai.agent.quantitative_scores_prompt")
    def test_non_numeric_or_out_of_range_scores_trigger_retry(
        self, mock_prompt, mock_parse, mock_encode
    ):
        """
        Scores must be numbers in 1-100 (the prompt's contract): a string or an
        out-of-range value must be rejected instead of flowing into numeric columns.
        """
        self.mock_ai_client.generate_content.return_value = "mock_response"
        for bad_value in ("high", 0, 250, True):
            with self.subTest(bad_value=bad_value):
                mock_parse.return_value = {
                    "AAPL": {
                        "momentum_score": bad_value,
                        "low_volatility_score": 60,
                        "risk_score": 40,
                    }
                }
                with self.assertRaises(RetryError):
                    self.agent._get_ai_scores([{"ticker": "AAPL", "company": "Apple"}])

    @patch("app.ai.agent.encode")
    @patch("app.ai.agent.ResponseParser.extract_and_decode_toon")
    @patch("app.ai.agent.quantitative_scores_prompt")
    def test_raises_invalid_response_error_when_response_is_empty(
        self, mock_prompt, mock_parse, mock_encode
    ):
        """
        Raises InvalidAIResponseError when the parsed AI response is empty.
        """
        self.mock_ai_client.generate_content.return_value = "mock_response"
        mock_parse.return_value = {}

        with self.assertRaises(RetryError):
            self.agent._get_ai_scores([{"ticker": "AAPL", "company": "Apple"}])

    @patch("app.ai.agent.encode")
    @patch("app.ai.agent.ResponseParser.extract_and_decode_toon")
    @patch("app.ai.agent.quantitative_scores_prompt")
    def test_raises_invalid_response_error_when_required_keys_missing(
        self, mock_prompt, mock_parse, mock_encode
    ):
        """
        Raises InvalidAIResponseError when any required score key is missing from the response.
        """
        incomplete_scores = {
            "AAPL": {"momentum_score": 0.8}
        }  # missing low_volatility_score, risk_score
        self.mock_ai_client.generate_content.return_value = "mock_response"
        mock_parse.return_value = incomplete_scores

        with self.assertRaises(RetryError):
            self.agent._get_ai_scores([{"ticker": "AAPL", "company": "Apple"}])


class TestRunStockDueDiligence(unittest.TestCase):
    def setUp(self):
        """
        Patches time.sleep and initializes AnalystAgent with mocked dependencies.
        """
        # Patch time.sleep to speed up tenacity retries (wait_fixed(1) would add ~4s per test)
        analysis_df = pd.DataFrame(
            {
                "Ticker": ["AAPL"],
                "High_Conviction_Count": [2],
                "Ownership_Delta_Avg": [0.5],
                "Portfolio_Concentration_Avg": [1.2],
            }
        )
        for patcher in (
            patch("time.sleep"),
            patch("app.ai.agent.quarter_analysis", return_value=analysis_df),
            patch("app.ai.agent.get_quarter_date", return_value="2023-12-31"),
        ):
            self.addCleanup(patcher.stop)
            patcher.start()
        self.mock_ai_client = MagicMock()
        self.agent = AnalystAgent("2023Q4", ai_client=self.mock_ai_client)

    @patch("app.ai.agent.stock_analysis")
    def test_returns_empty_dict_when_no_institutional_data(self, mock_stock_analysis):
        """
        Returns an empty dict when the ticker has no institutional filing data.
        """
        mock_stock_analysis.return_value = pd.DataFrame()

        result = self.agent.run_stock_due_diligence("UNKNOWN")

        self.assertEqual(result, {})

    @patch("app.ai.agent.PriceFetcher.get_current_price")
    @patch("app.ai.agent.stock_analysis")
    def test_returns_empty_dict_when_current_price_unavailable(
        self, mock_stock_analysis, mock_price
    ):
        """
        Returns an empty dict when the current price cannot be fetched.
        """
        mock_stock_analysis.return_value = _make_stock_df()
        mock_price.return_value = None

        result = self.agent.run_stock_due_diligence("AAPL")

        self.assertEqual(result, {})

    @patch("app.ai.agent.encode")
    @patch("app.ai.agent.ResponseParser.extract_and_decode_toon")
    @patch("app.ai.agent.stock_due_diligence_prompt")
    @patch("app.ai.agent.PriceFetcher.get_avg_price")
    @patch("app.ai.agent.PriceFetcher.get_current_price")
    @patch("app.ai.agent.stock_analysis")
    def test_returns_analysis_with_current_price_attached(
        self, mock_stock_analysis, mock_price, mock_avg_price, mock_prompt, mock_parse, mock_encode
    ):
        """
        Returns the parsed AI analysis dict with the current_price field added.
        """
        mock_stock_analysis.return_value = _make_stock_df()
        mock_price.return_value = 150.0
        mock_avg_price.return_value = 145.0
        self.mock_ai_client.generate_content.return_value = "mock_response"
        mock_parse.return_value = {"thesis": "Strong buy"}

        result = self.agent.run_stock_due_diligence("AAPL")

        self.assertIn("thesis", result)
        self.assertEqual(result["current_price"], "$150.00")

    @patch("app.ai.agent.encode")
    @patch("app.ai.agent.ResponseParser.extract_and_decode_toon")
    @patch("app.ai.agent.stock_due_diligence_prompt")
    @patch("app.ai.agent.PriceFetcher.get_avg_price")
    @patch("app.ai.agent.PriceFetcher.get_current_price")
    @patch("app.ai.agent.stock_analysis")
    def test_proceeds_without_filing_date_price(
        self, mock_stock_analysis, mock_price, mock_avg_price, mock_prompt, mock_parse, mock_encode
    ):
        """
        Returns a valid analysis even when the price on the filing date is unavailable.
        """
        mock_stock_analysis.return_value = _make_stock_df()
        mock_price.return_value = 150.0
        mock_avg_price.return_value = None  # filing date price not available
        self.mock_ai_client.generate_content.return_value = "mock_response"
        mock_parse.return_value = {"thesis": "Buy"}

        result = self.agent.run_stock_due_diligence("AAPL")

        self.assertIn("thesis", result)

    @patch("app.ai.agent.encode")
    @patch("app.ai.agent.ResponseParser.extract_and_decode_toon")
    @patch("app.ai.agent.stock_due_diligence_prompt")
    @patch("app.ai.agent.PriceFetcher.get_avg_price")
    @patch("app.ai.agent.PriceFetcher.get_current_price")
    @patch("app.ai.agent.stock_analysis")
    def test_raises_invalid_response_error_on_empty_ai_response(
        self, mock_stock_analysis, mock_price, mock_avg_price, mock_prompt, mock_parse, mock_encode
    ):
        """
        Raises InvalidAIResponseError (triggers retry) when the AI returns an empty TOON structure.
        """
        mock_stock_analysis.return_value = _make_stock_df()
        mock_price.return_value = 150.0
        mock_avg_price.return_value = 145.0
        self.mock_ai_client.generate_content.return_value = "mock_response"
        mock_parse.return_value = {}

        with self.assertRaises(RetryError):
            self.agent.run_stock_due_diligence("AAPL")

    @patch("app.ai.agent.encode")
    @patch("app.ai.agent.ResponseParser.extract_and_decode_toon")
    @patch("app.ai.agent.stock_due_diligence_prompt")
    @patch("app.ai.agent.PriceFetcher.get_avg_price")
    @patch("app.ai.agent.PriceFetcher.get_current_price")
    @patch("app.ai.agent.stock_analysis")
    def test_request_log_is_lazy_and_sanitises_ticker(
        self, mock_stock_analysis, mock_price, mock_avg_price, mock_prompt, mock_parse, mock_encode
    ):
        """
        The request log uses lazy formatting and strips control characters from the ticker.
        """
        mock_stock_analysis.return_value = _make_stock_df()
        mock_price.return_value = 150.0
        mock_avg_price.return_value = 145.0
        self.mock_ai_client.generate_content.return_value = "mock_response"
        self.mock_ai_client.get_model_name.return_value = "test-model"
        mock_parse.return_value = {"thesis": "Buy"}

        with self.assertLogs("app.ai.agent", level="DEBUG") as cm:
            self.agent.run_stock_due_diligence("AAA\nFAKE LOG LINE")

        record = next(r for r in cm.records if "due diligence on" in r.getMessage())
        self.assertTrue(record.args)
        self.assertNotIn("\n", record.getMessage())

    @patch("app.ai.agent.encode")
    @patch("app.ai.agent.ResponseParser.extract_and_decode_toon")
    @patch("app.ai.agent.stock_due_diligence_prompt")
    @patch("app.ai.agent.PriceFetcher.get_avg_price")
    @patch("app.ai.agent.PriceFetcher.get_current_price")
    @patch("app.ai.agent.stock_analysis")
    def test_retry_log_is_lazy(
        self, mock_stock_analysis, mock_price, mock_avg_price, mock_prompt, mock_parse, mock_encode
    ):
        """
        The before-sleep retry log passes its values as lazy %-format arguments.
        """
        mock_stock_analysis.return_value = _make_stock_df()
        mock_price.return_value = 150.0
        mock_avg_price.return_value = 145.0
        self.mock_ai_client.generate_content.return_value = "mock_response"
        mock_parse.return_value = {}

        with self.assertLogs("app.ai.agent", level="DEBUG") as cm, self.assertRaises(RetryError):
            self.agent.run_stock_due_diligence("AAPL")

        retry_records = [r for r in cm.records if "Retrying in" in r.getMessage()]
        self.assertTrue(retry_records)
        self.assertTrue(all(r.args for r in retry_records))


class TestReasoningLevelPerCall(unittest.TestCase):
    """
    Only the due-diligence call asks for a deeper reasoning level.
    """

    def setUp(self):
        """
        Builds an AnalystAgent around a mocked AI client.
        """
        analysis_df = pd.DataFrame(
            {
                "Ticker": ["AAPL"],
                "High_Conviction_Count": [2],
                "Ownership_Delta_Avg": [0.5],
                "Portfolio_Concentration_Avg": [1.2],
            }
        )
        for patcher in (
            patch("time.sleep"),
            patch("app.ai.agent.quarter_analysis", return_value=analysis_df),
            patch("app.ai.agent.get_quarter_date", return_value="2023-12-31"),
            patch("app.ai.agent.encode"),
            patch("app.ai.agent.promise_score_weights_prompt"),
            patch("app.ai.agent.quantitative_scores_prompt"),
            patch("app.ai.agent.stock_due_diligence_prompt"),
            patch("app.ai.agent.PriceFetcher.get_avg_price", return_value=145.0),
            patch("app.ai.agent.PriceFetcher.get_current_price", return_value=150.0),
            patch("app.ai.agent.stock_analysis", return_value=_make_stock_df()),
        ):
            self.addCleanup(patcher.stop)
            patcher.start()
        parse_patcher = patch("app.ai.agent.ResponseParser.extract_and_decode_toon")
        self.addCleanup(parse_patcher.stop)
        self.mock_parse = parse_patcher.start()
        self.mock_ai_client = MagicMock()
        self.mock_ai_client.generate_content.return_value = "mock_response"
        self.agent = AnalystAgent("2023Q4", ai_client=self.mock_ai_client)

    def test_due_diligence_requests_medium_reasoning(self):
        """
        The due-diligence prompt is open-ended, so it asks for medium reasoning.
        """
        self.mock_parse.return_value = {"thesis": "Buy"}

        self.agent.run_stock_due_diligence("AAPL")

        self.assertEqual(
            self.mock_ai_client.generate_content.call_args.kwargs, {"reasoning": "medium"}
        )

    def test_weights_call_keeps_default_reasoning(self):
        """
        The weights call does not override the client's default level.
        """
        self.mock_parse.return_value = _six_weights()

        self.agent._get_promise_score_weights()

        self.assertNotIn("reasoning", self.mock_ai_client.generate_content.call_args.kwargs)

    def test_scores_call_keeps_default_reasoning(self):
        """
        The scores call does not override the client's default level.
        """
        self.mock_parse.return_value = {
            "AAPL": {"momentum_score": 80, "low_volatility_score": 60, "risk_score": 40}
        }

        self.agent._get_ai_scores([{"ticker": "AAPL", "company": "Apple"}])

        self.assertNotIn("reasoning", self.mock_ai_client.generate_content.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()

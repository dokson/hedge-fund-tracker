import unittest

from app.ai.prompts import (
    promise_score_weights_prompt,
    quantitative_scores_prompt,
    stock_due_diligence_prompt,
)


class TestPromiseScoreWeightsPrompt(unittest.TestCase):
    def setUp(self):
        self.prompt = promise_score_weights_prompt("2023Q4")

    def test_interpolates_the_quarter(self):
        """
        The quarter reaches the model: the caller passes nothing else.
        """
        self.assertIn("2023Q4", self.prompt)

    def test_states_the_percentile_rank_transform(self):
        """
        Weights are applied to percentile ranks, not raw values. Hiding that
        changes the right answer, so the statement must survive edits.
        """
        self.assertIn("PERCENTILE RANK", self.prompt)

    def test_states_both_sign_rules(self):
        """
        The sign rule the code enforces is two-sided: negative on the selling
        metrics, strictly positive everywhere else.
        """
        self.assertIn("Seller_Count", self.prompt)
        self.assertIn("Close_Count", self.prompt)
        self.assertIn("negative weight", self.prompt)
        self.assertIn("strictly positive", self.prompt)

    def test_states_the_metric_count_range(self):
        """
        Mirrors PromiseScoreValidator.MIN_METRICS / MAX_METRICS.
        """
        self.assertIn("between 6 and 10 metrics", self.prompt)

    def test_keeps_a_toon_example(self):
        """
        The parser reads the last fenced toon block, so the format lock stays.
        """
        self.assertIn("```toon", self.prompt)

    def test_drops_the_self_validation_ritual(self):
        """
        Self-checked arithmetic was replaced by the validators plus the retry loop.
        """
        self.assertNotIn("Self-Correction", self.prompt)
        self.assertNotIn("internal validation", self.prompt)

    def test_labels_the_example_as_illustrative(self):
        """
        Weak models copy an unlabelled example verbatim instead of choosing their own weights.
        """
        self.assertIn(
            "EXAMPLE (illustrative format only; choose your own metrics and values)", self.prompt
        )

    def test_example_weights_satisfy_the_validator(self):
        """
        Models copy the example, so the example itself must pass every check.
        """
        from app.ai.promise_score_validator import PromiseScoreValidator

        weights = self._example_weights()
        self.assertEqual(PromiseScoreValidator.validate_metric_count(weights), "")
        self.assertEqual(PromiseScoreValidator.validate_weight_signs(weights), [])
        self.assertEqual(PromiseScoreValidator.validate_metrics(list(weights)), [])
        self.assertEqual(PromiseScoreValidator.validate_weight_values(weights), [])

    def test_example_weights_deliberately_do_not_sum_to_one(self):
        """
        An example summing to 1.0 would re-teach the retired sum constraint.
        """
        self.assertNotAlmostEqual(sum(self._example_weights().values()), 1.0, places=2)

    def test_example_keeps_negative_selling_weights(self):
        """
        The example shows the sign rule in action on both selling metrics.
        """
        weights = self._example_weights()
        self.assertLess(weights["Seller_Count"], 0)
        self.assertLess(weights["Close_Count"], 0)

    def test_drops_the_sum_constraint(self):
        """
        Code normalizes the weights, so the model is no longer asked for a fixed total.
        """
        self.assertNotIn("sum to 1.0", self.prompt)
        self.assertNotIn("negative ones included", self.prompt)
        self.assertNotIn("to compensate", self.prompt)
        self.assertNotIn("sum constraint", self.prompt)

    def test_states_weights_are_relative_and_normalized(self):
        """
        The model must know only the ratios between weights matter.
        """
        self.assertIn("relative to each other", self.prompt)
        self.assertIn("normalized", self.prompt)

    def _example_weights(self) -> dict[str, float]:
        """
        Decodes the illustrative example block of the prompt into float weights.
        """
        from app.ai.response_parser import ResponseParser

        example = self.prompt.split("EXAMPLE (illustrative", 1)[1]
        return {k: float(v) for k, v in ResponseParser.extract_and_decode_toon(example).items()}

    def test_describes_consequences_without_a_hard_demand(self):
        """
        The rank-transform consequences are explanations, not an extra constraint.
        """
        self.assertIn("Two consequences follow", self.prompt)
        self.assertNotIn("MUST shape your choice", self.prompt)


class TestQuantitativeScoresPrompt(unittest.TestCase):
    def setUp(self):
        self.prompt = quantitative_scores_prompt("AAPL:\n  ticker: AAPL", "2023-12-31")

    def test_interpolates_the_context_and_filing_date(self):
        self.assertIn("AAPL:", self.prompt)
        self.assertIn("2023-12-31", self.prompt)

    def test_does_not_claim_real_time_market_data(self):
        """
        The model gets two prices and a percentage, nothing else: claiming a
        market data feed invites fabricated figures.
        """
        self.assertNotIn("real-time", self.prompt)
        self.assertIn("no other market data", self.prompt)

    def test_names_the_fields_the_model_actually_receives(self):
        for field in ("company name", "current price", "percentage change"):
            self.assertIn(field, self.prompt)

    def test_asks_to_refine_the_sector_into_an_industry(self):
        """
        The field is filled from YFinance's industry when available and from the
        sector otherwise, so the instruction must cover the sector case.
        """
        self.assertIn("SECTOR", self.prompt)
        self.assertIn("Yahoo Finance INDUSTRY", self.prompt)
        self.assertIn('"ETF"', self.prompt)

    def test_states_the_score_directions(self):
        self.assertIn("MOMENTUM_SCORE (1-100, HIGH IS GOOD)", self.prompt)
        self.assertIn("LOW_VOLATILITY_SCORE (1-100, HIGH IS GOOD)", self.prompt)
        self.assertIn("RISK_SCORE (1-100, HIGH IS BAD", self.prompt)

    def test_makes_momentum_relative_to_the_list(self):
        self.assertIn("RELATIVE TO THE OTHER STOCKS IN THIS LIST", self.prompt)

    def test_frames_calibration_as_illustrative(self):
        """
        Dated anchors ("NVDA momentum 95") dragged every semiconductor upward.
        """
        self.assertIn("illustrative profiles", self.prompt)

    def test_example_block_uses_placeholder_tickers(self):
        """
        The example must not anchor scores on real companies, but keeps the quoted-hyphen case.
        """
        example = self.prompt.split("EXAMPLE", 1)[1]
        self.assertNotIn("NVDA", self.prompt)
        self.assertNotIn("BRK-B", example)
        self.assertIn("AAA:", example)
        self.assertIn('"BBB-B":', example)

    def test_keeps_the_toon_output_lock(self):
        self.assertIn("```toon", self.prompt)
        for field in ("momentum_score", "low_volatility_score", "risk_score", "industry"):
            self.assertIn(field, self.prompt)


class TestStockDueDiligencePrompt(unittest.TestCase):
    def setUp(self):
        self.prompt = stock_due_diligence_prompt('ticker: "XYZ"')

    def test_does_not_claim_live_data_access(self):
        """
        The model only receives the TOON context, so the prompt must not promise live data.
        """
        self.assertNotIn("real-time", self.prompt)
        self.assertIn("no live market data", self.prompt)

    def test_has_no_self_correction_instruction(self):
        """
        Validation and retries happen in code; the prompt must not ask the model to regenerate.
        """
        self.assertNotIn("self-correct", self.prompt)

    def test_example_uses_a_placeholder_ticker(self):
        """
        The worked example shows the shape only, with no real company to copy from.
        """
        self.assertNotIn("NVDA", self.prompt)
        self.assertIn("illustrative", self.prompt)

    def test_does_not_demand_data_the_model_lacks(self):
        """
        Financials, news and current market conditions are not in the context, so they are not demanded.
        """
        self.assertNotIn("financials, valuation, news", self.prompt)
        self.assertNotIn("current market conditions", self.prompt)
        self.assertNotIn("Reference at least one common valuation multiple", self.prompt)
        self.assertIn("Interpret everything else you know about the company", self.prompt)
        self.assertIn("your general knowledge of the company's fundamentals", self.prompt)

    def test_valuation_multiple_is_optional(self):
        """
        A multiple is cited only when known with confidence; otherwise valuation is qualitative.
        """
        self.assertIn(
            "Cite a valuation multiple versus peers only if you know it with confidence; "
            "otherwise assess valuation qualitatively.",
            self.prompt,
        )

    def test_financial_metrics_are_mentioned_only_when_known(self):
        """
        Financial Health must not force the model to produce figures it does not have.
        """
        self.assertIn("only if you know them", self.prompt)

    def test_interpolates_the_context(self):
        """
        The stock context reaches the model.
        """
        self.assertIn('ticker: "XYZ"', self.prompt)


if __name__ == "__main__":
    unittest.main()

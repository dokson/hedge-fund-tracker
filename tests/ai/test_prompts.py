import unittest

from app.ai.prompts import promise_score_weights_prompt, quantivative_scores_prompt


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


class TestQuantitativeScoresPrompt(unittest.TestCase):
    def setUp(self):
        self.prompt = quantivative_scores_prompt("AAPL:\n  ticker: AAPL", "2023-12-31")

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

    def test_keeps_the_toon_output_lock(self):
        self.assertIn("```toon", self.prompt)
        for field in ("momentum_score", "low_volatility_score", "risk_score", "industry"):
            self.assertIn(field, self.prompt)


if __name__ == "__main__":
    unittest.main()

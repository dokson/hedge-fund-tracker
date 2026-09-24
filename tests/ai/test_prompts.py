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

    def test_input_metrics_stay_in_a_toon_block(self):
        """
        TOON is kept for compact prompt inputs, but no longer asked for as the answer.
        """
        self.assertIn("```toon", self.prompt)
        self.assertNotIn("Return ONLY a single ```toon", self.prompt)

    def test_describes_the_json_output_fields(self):
        """
        The schema carries the structure; the prompt names the fields it fills.
        """
        for field in ("JSON", "`weights`", "`metric`", "`weight`"):
            self.assertIn(field, self.prompt)

    def test_drops_the_self_validation_ritual(self):
        """
        Self-checked arithmetic was replaced by the validators plus the retry loop.
        """
        self.assertNotIn("Self-Correction", self.prompt)
        self.assertNotIn("internal validation", self.prompt)

    def test_has_no_worked_weights_example(self):
        """
        A single numeric example was copied verbatim by weak models; the schema carries the shape.
        """
        self.assertNotIn("EXAMPLE", self.prompt)
        self.assertNotIn('"weight": ', self.prompt)

    def test_states_the_sign_rule_in_text(self):
        """
        Without an example, the negative-weight rule for selling metrics must be spelled out.
        """
        self.assertIn("Seller_Count", self.prompt)
        self.assertIn("Close_Count", self.prompt)
        self.assertIn("negative", self.prompt)

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

    def test_states_the_score_direction(self):
        """
        Risk is the one LLM score and high means bad.
        """
        self.assertIn("RISK_SCORE (1-100, HIGH IS BAD)", self.prompt)

    def test_frames_calibration_as_illustrative(self):
        """
        Dated anchors ("NVDA momentum 95") dragged every semiconductor upward.
        """
        self.assertIn("illustrative profiles", self.prompt)

    def test_uses_no_real_tickers(self):
        """
        Nothing in the prompt may anchor scores on a real company.
        """
        self.assertNotIn("NVDA", self.prompt)
        self.assertNotIn("BRK-B", self.prompt)

    def test_input_stays_toon_and_output_is_json(self):
        """
        The stock list is sent as TOON; the answer is a JSON list of stocks.
        """
        self.assertIn("```toon", self.prompt)
        self.assertNotIn("Return ONLY a single ```toon", self.prompt)
        self.assertIn("JSON", self.prompt)
        self.assertIn("`stocks`", self.prompt)
        for field in ("ticker", "risk_score", "industry"):
            self.assertIn(f"`{field}`", self.prompt)

    def test_no_longer_asks_for_price_derived_scores(self):
        """
        Momentum and low volatility are computed from price history, not by the LLM.
        """
        lowered = self.prompt.lower()
        for word in ("momentum", "volatility"):
            self.assertNotIn(word, lowered)

    def test_asks_for_every_ticker_exactly_once(self):
        """
        Missing or duplicated tickers are rejected by the agent.
        """
        self.assertIn("exactly once", self.prompt)
        self.assertIn("spelled exactly as provided", self.prompt)


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

    def test_uses_no_real_ticker(self):
        """
        No real company is offered as something to copy from.
        """
        self.assertNotIn("NVDA", self.prompt)

    def test_input_stays_toon_and_output_is_json(self):
        """
        The context is sent as TOON; the answer is described as JSON fields.
        """
        self.assertIn("```toon", self.prompt)
        self.assertNotIn("Return ONLY a single ```toon", self.prompt)
        self.assertIn("JSON", self.prompt)
        for field in ("analysis", "investment_thesis", "overall_sentiment", "price_target"):
            self.assertIn(f"`{field}`", self.prompt)

    def test_keeps_the_null_and_sentiment_rules(self):
        """
        The schema allows null; the prompt says when to use it.
        """
        self.assertIn("`null`", self.prompt)
        for sentiment in ("Bullish", "Neutral", "Bearish"):
            self.assertIn(sentiment, self.prompt)

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


# Keywords accepted by both OpenAI-style strict json_schema and Gemini's response_json_schema.
_STRICT_KEYWORDS = frozenset(
    {
        "type",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "enum",
        "description",
        "minimum",
        "maximum",
        "minItems",
        "maxItems",
    }
)
_JSON_TYPES = frozenset({"object", "array", "string", "number", "integer", "boolean", "null"})


class TestResponseSchemas(unittest.TestCase):
    """
    Each schema must stay inside the strict subset both providers enforce.
    """

    def assert_strict(self, schema: dict, path: str = "$") -> None:
        """
        Walks ``schema`` asserting the strict-mode rules at every node.
        """
        self.assertLessEqual(set(schema), _STRICT_KEYWORDS, path)
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        self.assertLessEqual(set(types), _JSON_TYPES, path)
        if "enum" in schema:
            for value in schema["enum"]:
                self.assertIn("null" if value is None else type(value).__name__, {"str", "null"})
                if value is None:
                    self.assertIn("null", types, path)
        if "object" in types:
            self.assertIs(schema["additionalProperties"], False, path)
            self.assertEqual(set(schema["required"]), set(schema["properties"]), path)
            for name, child in schema["properties"].items():
                self.assert_strict(child, f"{path}.{name}")
        if "array" in types:
            self.assert_strict(schema["items"], f"{path}[]")

    def schemas(self) -> dict:
        """
        The three response schemas, by name.
        """
        from app.ai.prompts import DUE_DILIGENCE_SCHEMA, SCORES_SCHEMA, WEIGHTS_SCHEMA

        return {
            "weights": WEIGHTS_SCHEMA,
            "scores": SCORES_SCHEMA,
            "due_diligence": DUE_DILIGENCE_SCHEMA,
        }

    def test_schemas_are_strict_and_json_serializable(self):
        """
        Root objects, closed and fully required, and serializable as sent on the wire.
        """
        import json

        for name, schema in self.schemas().items():
            with self.subTest(schema=name):
                self.assertEqual(schema["type"], "object")
                self.assert_strict(schema)
                self.assertEqual(json.loads(json.dumps(schema)), schema)

    def test_weights_schema_enumerates_the_available_metrics(self):
        """
        The metric enum and the item bounds mirror the validator.
        """
        from app.ai.promise_score_validator import PromiseScoreValidator as V

        weights = self.schemas()["weights"]["properties"]["weights"]
        self.assertEqual(weights["items"]["properties"]["metric"]["enum"], V.AVAILABLE_METRICS)
        self.assertEqual(weights["minItems"], V.MIN_METRICS)
        self.assertEqual(weights["maxItems"], V.MAX_METRICS)

    def test_scores_schema_lists_stocks_with_bounded_integer_scores(self):
        """
        Tickers are values in a list, so hyphens and dots need no quoting rules.
        """
        stock = self.schemas()["scores"]["properties"]["stocks"]["items"]
        self.assertEqual(stock["properties"]["ticker"]["type"], "string")
        self.assertEqual(set(stock["properties"]), {"ticker", "industry", "risk_score"})
        self.assertEqual(set(stock["required"]), {"ticker", "industry", "risk_score"})
        risk = stock["properties"]["risk_score"]
        self.assertEqual((risk["type"], risk["minimum"], risk["maximum"]), ("integer", 1, 100))

    def test_due_diligence_schema_keeps_the_api_shape(self):
        """
        The frontend reads these exact keys, so the shape must not drift.
        """
        schema = self.schemas()["due_diligence"]
        self.assertEqual(
            set(schema["properties"]), {"ticker", "company", "analysis", "investment_thesis"}
        )
        analysis = schema["properties"]["analysis"]["properties"]
        self.assertEqual(
            set(analysis),
            {
                "business_summary",
                "financial_health",
                "financial_health_sentiment",
                "valuation",
                "valuation_sentiment",
                "growth_vs_risks",
                "growth_vs_risks_sentiment",
                "institutional_sentiment",
                "institutional_sentiment_sentiment",
            },
        )
        thesis = schema["properties"]["investment_thesis"]["properties"]
        self.assertEqual(set(thesis), {"overall_sentiment", "thesis", "price_target"})
        self.assertEqual(
            thesis["overall_sentiment"]["enum"], ["Bullish", "Neutral", "Bearish", None]
        )


if __name__ == "__main__":
    unittest.main()

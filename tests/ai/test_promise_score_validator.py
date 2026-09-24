import unittest

from app.ai.promise_score_validator import PromiseScoreValidator, normalize_weights


class TestPromiseScoreValidatorInit(unittest.TestCase):
    def test_stores_default_top_n_stocks(self):
        """
        Stores 30 as the default value for top_n_stocks.
        """
        validator = PromiseScoreValidator()

        self.assertEqual(validator.top_n_stocks, 30)

    def test_stores_custom_top_n_stocks(self):
        """
        Stores the provided top_n_stocks value when given explicitly.
        """
        validator = PromiseScoreValidator(top_n_stocks=10)

        self.assertEqual(validator.top_n_stocks, 10)


class TestValidateWeightValues(unittest.TestCase):
    def test_accepts_finite_non_zero_weights_with_a_positive_one(self):
        """
        Arbitrary magnitudes are fine: normalization happens downstream.
        """
        weights = {"Holder_Count": 3.0, "Net_Buyers": 0.4, "Seller_Count": -2.0}

        self.assertEqual(PromiseScoreValidator.validate_weight_values(weights), [])

    def test_rejects_a_zero_weight(self):
        """
        A zero weight means the metric should have been omitted.
        """
        errors = PromiseScoreValidator.validate_weight_values({"Holder_Count": 1.0, "Delta": 0.0})

        self.assertTrue(any("Delta" in e for e in errors))

    def test_rejects_nan_and_infinite_weights(self):
        """
        Non-finite weights would poison the normalization.
        """
        errors = PromiseScoreValidator.validate_weight_values(
            {"Holder_Count": 1.0, "Delta": float("nan"), "Total_Value": float("inf")}
        )

        self.assertTrue(any("Delta" in e for e in errors))
        self.assertTrue(any("Total_Value" in e for e in errors))

    def test_rejects_only_negative_weights(self):
        """
        With no positive weight the score could only penalize selling.
        """
        errors = PromiseScoreValidator.validate_weight_values(
            {"Seller_Count": -1.0, "Close_Count": -0.5}
        )

        self.assertTrue(any("positive" in e for e in errors))


class TestNormalizeWeights(unittest.TestCase):
    def test_divides_by_the_sum_of_absolute_values(self):
        """
        Positive-only weights become fractions of their total.
        """
        result = normalize_weights({"A": 3.0, "B": 1.0})

        self.assertAlmostEqual(result["A"], 0.75)
        self.assertAlmostEqual(result["B"], 0.25)

    def test_keeps_signs_with_mixed_weights(self):
        """
        Absolute values sum to 1 and each sign survives.
        """
        result = normalize_weights({"A": 6.0, "B": 2.0, "C": -2.0})

        self.assertAlmostEqual(result["A"], 0.6)
        self.assertAlmostEqual(result["B"], 0.2)
        self.assertAlmostEqual(result["C"], -0.2)
        self.assertAlmostEqual(sum(abs(v) for v in result.values()), 1.0)

    def test_raises_when_all_weights_are_zero(self):
        """
        There is nothing to normalize by.
        """
        with self.assertRaises(ValueError):
            normalize_weights({"A": 0.0, "B": 0.0})

    def test_raises_on_empty_weights(self):
        """
        An empty mapping has a zero absolute sum.
        """
        with self.assertRaises(ValueError):
            normalize_weights({})


class TestPromiseScoreValidatorValidateWeightSigns(unittest.TestCase):
    def test_returns_empty_list_for_correctly_signed_weights(self):
        """
        Positive weights on positive metrics and negative weights on the
        selling metrics pass with no offenders.
        """
        weights = {"Holder_Count": 0.8, "Net_Buyers": 0.4, "Seller_Count": -0.2}

        result = PromiseScoreValidator.validate_weight_signs(weights)

        self.assertEqual(result, [])

    def test_flags_positive_weight_on_selling_metric(self):
        """
        A positive Seller_Count weight would reward institutional selling:
        it must be reported as an offender.
        """
        weights = {"Seller_Count": 0.6, "Holder_Count": 0.4}

        result = PromiseScoreValidator.validate_weight_signs(weights)

        self.assertEqual(result, ["Seller_Count"])

    def test_flags_negative_weight_on_positive_metric(self):
        """
        A negative weight on a conviction metric inverts the ranking intent:
        it must be reported as an offender.
        """
        weights = {"High_Conviction_Count": -0.5, "Net_Buyers": 1.5}

        result = PromiseScoreValidator.validate_weight_signs(weights)

        self.assertEqual(result, ["High_Conviction_Count"])

    def test_flags_positive_close_count(self):
        """
        Close_Count is the other must-be-negative metric from the prompt.
        """
        weights = {"Close_Count": 0.2, "Holder_Count": 0.8}

        result = PromiseScoreValidator.validate_weight_signs(weights)

        self.assertEqual(result, ["Close_Count"])


class TestPromiseScoreValidatorValidateMetrics(unittest.TestCase):
    def test_returns_empty_list_when_all_metrics_are_valid(self):
        """
        Returns an empty list when every metric is in AVAILABLE_METRICS.
        """
        metrics = ["Total_Value", "Delta", "Buyer_Count"]

        result = PromiseScoreValidator.validate_metrics(metrics)

        self.assertEqual(result, [])

    def test_returns_invalid_metrics(self):
        """
        Returns a list containing only the unrecognized metric names.
        """
        metrics = ["Total_Value", "NonExistentMetric", "AnotherBadOne"]

        result = PromiseScoreValidator.validate_metrics(metrics)

        self.assertEqual(result, ["NonExistentMetric", "AnotherBadOne"])

    def test_returns_empty_list_for_empty_input(self):
        """
        Returns an empty list when given an empty metrics list.
        """
        result = PromiseScoreValidator.validate_metrics([])

        self.assertEqual(result, [])

    def test_all_available_metrics_are_valid(self):
        """
        Returns an empty list when the full AVAILABLE_METRICS list is validated.
        """
        result = PromiseScoreValidator.validate_metrics(PromiseScoreValidator.AVAILABLE_METRICS)

        self.assertEqual(result, [])


class TestValidateMetricCount(unittest.TestCase):
    def test_accepts_counts_inside_the_range(self):
        """
        Returns an empty message for any count between MIN_METRICS and MAX_METRICS.
        """
        for count in range(
            PromiseScoreValidator.MIN_METRICS, PromiseScoreValidator.MAX_METRICS + 1
        ):
            weights = {f"Metric{i}": 0.1 for i in range(count)}

            self.assertEqual(PromiseScoreValidator.validate_metric_count(weights), "")

    def test_rejects_too_few_metrics(self):
        """
        Returns an explanatory message naming the minimum when too few metrics are used.
        """
        weights = {f"Metric{i}": 0.2 for i in range(PromiseScoreValidator.MIN_METRICS - 1)}

        message = PromiseScoreValidator.validate_metric_count(weights)

        self.assertIn(str(PromiseScoreValidator.MIN_METRICS), message)
        self.assertIn("minimum", message)

    def test_rejects_too_many_metrics(self):
        """
        Returns an explanatory message naming the maximum when too many metrics are used.
        """
        weights = {f"Metric{i}": 0.05 for i in range(PromiseScoreValidator.MAX_METRICS + 1)}

        message = PromiseScoreValidator.validate_metric_count(weights)

        self.assertIn(str(PromiseScoreValidator.MAX_METRICS), message)
        self.assertIn("maximum", message)


if __name__ == "__main__":
    unittest.main()

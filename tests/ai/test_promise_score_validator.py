import unittest
from app.ai.promise_score_validator import PromiseScoreValidator


class TestPromiseScoreValidatorInit(unittest.TestCase):

    def test_stores_default_top_n_stocks(self):
        """
        Stores 30 as the default value for top_n_stocks.
        """
        validator = PromiseScoreValidator()

        self.assertEqual(validator.top_n_stocks, 30)

    def test_stores_default_weight_tolerance(self):
        """
        Stores 0.05 as the default weight tolerance.
        """
        validator = PromiseScoreValidator()

        self.assertEqual(validator.weight_tolerance, 0.05)

    def test_stores_custom_top_n_stocks(self):
        """
        Stores the provided top_n_stocks value when given explicitly.
        """
        validator = PromiseScoreValidator(top_n_stocks=10)

        self.assertEqual(validator.top_n_stocks, 10)

    def test_stores_custom_weight_tolerance(self):
        """
        Stores the provided weight_tolerance value when given explicitly.
        """
        validator = PromiseScoreValidator(weight_tolerance=0.1)

        self.assertEqual(validator.weight_tolerance, 0.1)


class TestPromiseScoreValidatorValidateWeights(unittest.TestCase):

    def test_returns_true_when_weights_sum_to_exactly_one(self):
        """
        Returns True when weights sum to exactly 1.0.
        """
        weights = {'Total_Value': 0.5, 'Delta': 0.5}

        result = PromiseScoreValidator.validate_weights(weights)

        self.assertTrue(result)

    def test_returns_true_when_sum_within_default_tolerance(self):
        """
        Returns True when the sum is within the default 0.05 tolerance (e.g. 0.98).
        """
        weights = {'Total_Value': 0.5, 'Delta': 0.48}  # sum = 0.98

        result = PromiseScoreValidator.validate_weights(weights)

        self.assertTrue(result)

    def test_returns_true_when_sum_at_upper_tolerance_boundary(self):
        """
        Returns True when the sum equals exactly 1.0 + tolerance.
        """
        weights = {'Total_Value': 0.5, 'Delta': 0.55}  # sum = 1.05

        result = PromiseScoreValidator.validate_weights(weights)

        self.assertTrue(result)

    def test_returns_true_when_sum_at_lower_tolerance_boundary(self):
        """
        Returns True when the sum equals exactly 1.0 - tolerance.
        """
        weights = {'Total_Value': 0.5, 'Delta': 0.45}  # sum = 0.95

        result = PromiseScoreValidator.validate_weights(weights)

        self.assertTrue(result)

    def test_returns_false_when_sum_exceeds_upper_tolerance(self):
        """
        Returns False when the sum exceeds 1.0 + tolerance.
        """
        weights = {'Total_Value': 0.6, 'Delta': 0.5}  # sum = 1.1

        result = PromiseScoreValidator.validate_weights(weights)

        self.assertFalse(result)

    def test_returns_false_when_sum_below_lower_tolerance(self):
        """
        Returns False when the sum is below 1.0 - tolerance.
        """
        weights = {'Total_Value': 0.4, 'Delta': 0.4}  # sum = 0.8

        result = PromiseScoreValidator.validate_weights(weights)

        self.assertFalse(result)

    def test_respects_custom_tolerance_parameter(self):
        """
        Uses the provided tolerance instead of the default 0.05.
        """
        weights = {'Total_Value': 0.7, 'Delta': 0.5}  # sum = 1.2

        result = PromiseScoreValidator.validate_weights(weights, tolerance=0.25)

        self.assertTrue(result)


class TestPromiseScoreValidatorValidateMetrics(unittest.TestCase):

    def test_returns_empty_list_when_all_metrics_are_valid(self):
        """
        Returns an empty list when every metric is in AVAILABLE_METRICS.
        """
        metrics = ['Total_Value', 'Delta', 'Buyer_Count']

        result = PromiseScoreValidator.validate_metrics(metrics)

        self.assertEqual(result, [])

    def test_returns_invalid_metrics(self):
        """
        Returns a list containing only the unrecognized metric names.
        """
        metrics = ['Total_Value', 'NonExistentMetric', 'AnotherBadOne']

        result = PromiseScoreValidator.validate_metrics(metrics)

        self.assertEqual(result, ['NonExistentMetric', 'AnotherBadOne'])

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


if __name__ == '__main__':
    unittest.main()

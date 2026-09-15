import unittest

from app.analysis.depositary import listed_units


class TestListedUnits(unittest.TestCase):
    def test_converts_by_the_confirmed_ratio_when_it_is_unambiguous(self):
        # 24.7M ordinary reported as 12.7% of a class listed as 39.76M receipts
        # implies five ordinary each; the filed count divided by five is exact,
        # where the reported percentage is only good to one decimal.
        self.assertEqual(listed_units(24_699_825, 12.7, 39_759_402), 4_939_965)

    def test_falls_back_to_the_percentage_when_the_ratio_is_ambiguous(self):
        # Around 27, neighbouring integer ratios sit ~3.7% apart, inside the
        # measurement error, so no integer can be confirmed. The stake is then
        # taken straight from the percentage of the class.
        self.assertEqual(listed_units(131_628_075, 7.1, 68_861_195), 4_889_145)

    def test_an_ordinary_listing_is_left_at_its_filed_count(self):
        self.assertIsNone(listed_units(1_000_000, 5.0, 20_000_000))

    def test_a_small_discrepancy_is_not_a_depositary_structure(self):
        # 1.2x is a stale share count or a rounded percentage, not a ratio.
        self.assertIsNone(listed_units(1_200_000, 5.0, 20_000_000))

    def test_missing_percentage_means_no_conversion(self):
        self.assertIsNone(listed_units(24_699_825, None, 39_759_402))
        self.assertIsNone(listed_units(24_699_825, float("nan"), 39_759_402))

    def test_missing_share_count_means_no_conversion(self):
        self.assertIsNone(listed_units(24_699_825, 12.7, None))

    def test_non_positive_inputs_mean_no_conversion(self):
        self.assertIsNone(listed_units(0, 12.7, 39_759_402))
        self.assertIsNone(listed_units(24_699_825, 0.0, 39_759_402))
        self.assertIsNone(listed_units(24_699_825, 12.7, 0))

    def test_a_percentage_above_one_hundred_is_rejected(self):
        self.assertIsNone(listed_units(24_699_825, 150.0, 39_759_402))

    def test_a_stake_can_never_exceed_the_class(self):
        # A conversion implying more units than exist is not a conversion.
        self.assertIsNone(listed_units(24_699_825, 99.9, 1_000))


if __name__ == "__main__":
    unittest.main()

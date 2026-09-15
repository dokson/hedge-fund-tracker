import unittest

from app.utils.numbers import snap_to_simple_ratio


class TestSnapToSimpleRatio(unittest.TestCase):
    def test_snaps_a_near_integer_upwards(self):
        self.assertEqual(snap_to_simple_ratio(4.98), 5.0)

    def test_snaps_a_near_integer_downwards(self):
        self.assertEqual(snap_to_simple_ratio(3.0005), 3.0)

    def test_snaps_a_reciprocal(self):
        self.assertEqual(snap_to_simple_ratio(0.1998), 0.2)

    def test_prefers_the_smallest_denominator(self):
        self.assertEqual(snap_to_simple_ratio(1.4999), 1.5)

    def test_rejects_a_ratio_that_is_simple_only_over_a_large_denominator(self):
        # 249/50 is not a simple ratio: a numerator bound is what excludes it.
        self.assertEqual(snap_to_simple_ratio(4.98, tolerance=0.0001), 4.98)

    def test_leaves_a_value_no_simple_ratio_is_near(self):
        # 2.39 is within 1% of 12/5, so only a caller that bounds the
        # denominator gets it back untouched.
        self.assertEqual(snap_to_simple_ratio(2.39, max_denominator=2), 2.39)
        self.assertEqual(snap_to_simple_ratio(2.39), 2.4)

    def test_honours_a_wider_tolerance(self):
        self.assertEqual(snap_to_simple_ratio(4.89, tolerance=0.05), 5.0)

    def test_rejects_non_positive_values(self):
        self.assertEqual(snap_to_simple_ratio(0.0), 0.0)
        self.assertEqual(snap_to_simple_ratio(-3.0), -3.0)


if __name__ == "__main__":
    unittest.main()

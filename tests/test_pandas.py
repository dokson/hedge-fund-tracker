import unittest
import pandas as pd
import numpy as np
from scraper.pandas import coalesce

class TestPandas(unittest.TestCase):

    def test_coalesce(self):
        """
        Tests the coalesce function with various scenarios.
        """
        # Scenario 1: Basic two-series coalesce
        s1 = pd.Series([1, None, 3, None], dtype='Int64')
        s2 = pd.Series([None, 2, None, 4], dtype='Int64')
        expected1 = pd.Series([1, 2, 3, 4], dtype='Int64')
        result1 = coalesce(s1, s2)
        pd.testing.assert_series_equal(result1, expected1, check_names=False)

        # Scenario 2: Three series, filling gaps sequentially
        s3 = pd.Series([None, None, 30, None], dtype='Int64')
        expected2 = pd.Series([1, 2, 3, 4], dtype='Int64') # s1 fills first, then s2
        result2 = coalesce(s1, s2, s3)
        pd.testing.assert_series_equal(result2, expected2, check_names=False)

        # Scenario 3: First series is complete, no changes should occur
        s_full = pd.Series([1, 2, 3], dtype='Int64')
        s_other = pd.Series([4, 5, 6], dtype='Int64')
        # The result should be a copy of the original series
        expected3 = pd.Series([1, 2, 3], dtype='Int64')
        result3 = coalesce(s_full, s_other)
        pd.testing.assert_series_equal(result3, expected3, check_names=False)

        # Scenario 4: Result still contains None values because no series can fill it
        s4 = pd.Series([4, None, 5, None], dtype='Int64')
        result4 = coalesce(s1, s4)
        # The result should be a copy of the original series
        expected4 = s1.copy()
        pd.testing.assert_series_equal(result4, expected4, check_names=False)


if __name__ == '__main__':
    unittest.main()
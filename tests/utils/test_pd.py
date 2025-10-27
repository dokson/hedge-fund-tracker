from app.utils.pd import coalesce, format_value_series, get_numeric_series, get_percentage_number_series
import pandas as pd
import numpy as np
import unittest


class TestPandas(unittest.TestCase):

    def test_coalesce(self):
        """
        Tests the coalesce function with various scenarios.
        """
        s1 = pd.Series([1, np.nan, 3])
        s2 = pd.Series([np.nan, 2, np.nan])
        s3 = pd.Series([10, 20, 30])

        # Test with two series
        result = coalesce(s1, s2)
        expected = pd.Series([1.0, 2.0, 3.0])
        pd.testing.assert_series_equal(result, expected)

        # Test with three series
        result = coalesce(s1, s2, s3)
        expected = pd.Series([1.0, 2.0, 3.0])
        pd.testing.assert_series_equal(result, expected)

        # Test where first series is all null
        s_null = pd.Series([np.nan, np.nan, np.nan])
        result = coalesce(s_null, s2, s3)
        expected = pd.Series([10.0, 2.0, 30.0])
        pd.testing.assert_series_equal(result, expected)


    def test_format_value_series(self):
        """
        Tests the vectorized format_value_series function.
        """
        input_series = pd.Series([210, -1234, 1234567, 9870123456, 1234567891011, 9999999999999, np.nan, np.inf])
        expected_output = pd.Series(['210', '-1.23K', '1.23M', '9.87B', '1.23T', '10T', 'N/A', '∞'])
        
        result = format_value_series(input_series)
        pd.testing.assert_series_equal(result, expected_output, check_names=False)


    def test_get_numeric_series(self):
        """
        Tests the vectorized get_numeric_series function.
        """
        input_series = pd.Series(['500', '-1.23K', '1.23M', '9.87B', '1.23T', 'N/A', '1.00M'])
        # Note: get_numeric returns int, so we expect float results from vectorized version due to NaN
        expected_output = pd.Series([500, -1230, 1230000, 9870000000, 1230000000000, np.nan, 1000000], dtype=float)
        
        result = get_numeric_series(input_series)
        pd.testing.assert_series_equal(result, expected_output, check_names=False)


    def test_get_percentage_number_series(self):
        """
        Tests the vectorized get_percentage_number_series function.
        """
        input_series = pd.Series(['12.3%', '100%', '<.01%', 'N/A', '-10.5%', '0%'])
        expected_output = pd.Series([12.3, 100.0, 0.0, np.nan, -10.5, 0.0])
        
        result = get_percentage_number_series(input_series)
        pd.testing.assert_series_equal(result, expected_output, check_names=False)


if __name__ == '__main__':
    unittest.main()
import unittest

import numpy as np
import pandas as pd

from app.utils.pd import (
    coalesce,
    escape_csv_text_columns,
    format_value_series,
    get_numeric_series,
    get_percentage_number_series,
)


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
        input_series = pd.Series(
            [210, -1234, 1234567, 9870123456, 1234567891011, 9999999999999, np.nan, np.inf]
        )
        expected_output = pd.Series(["210", "-1.23K", "1.23M", "9.87B", "1.23T", "10T", "N/A", "∞"])

        result = format_value_series(input_series)
        pd.testing.assert_series_equal(result, expected_output, check_names=False)

    def test_get_numeric_series(self):
        """
        Tests the vectorized get_numeric_series function.
        """
        input_series = pd.Series(["500", "-1.23K", "1.23M", "9.87B", "1.23T", "N/A", "1.00M"])
        # Note: get_numeric returns int, so we expect float results from vectorized version due to NaN
        expected_output = pd.Series(
            [500, -1230, 1230000, 9870000000, 1230000000000, np.nan, 1000000], dtype=float
        )

        result = get_numeric_series(input_series)
        pd.testing.assert_series_equal(result, expected_output, check_names=False)

    def test_get_percentage_number_series(self):
        """
        Tests the vectorized get_percentage_number_series function.
        """
        input_series = pd.Series(["12.3%", "100%", "<.01%", "N/A", "-10.5%", "0%"])
        expected_output = pd.Series([12.3, 100.0, 0.0, np.nan, -10.5, 0.0])

        result = get_percentage_number_series(input_series)
        pd.testing.assert_series_equal(result, expected_output, check_names=False)


class TestEscapeCsvTextColumns(unittest.TestCase):
    def test_escapes_company_but_not_numeric_columns(self):
        """
        Free-text columns (Company) are formula-escaped; numeric columns keep a
        legitimate leading '-' untouched (no corruption).
        """
        df = pd.DataFrame(
            {
                "Company": ["=evil()", "Acme Inc"],
                "Delta_Value": ["-1234", "5678"],
            }
        )

        result = escape_csv_text_columns(df)

        self.assertEqual(list(result["Company"]), ["'=evil()", "Acme Inc"])
        # Numeric-looking column must be left exactly as-is.
        self.assertEqual(list(result["Delta_Value"]), ["-1234", "5678"])

    def test_returns_copy_without_mutating_input(self):
        """The original DataFrame is not modified."""
        df = pd.DataFrame({"Company": ["=x"]})
        escape_csv_text_columns(df)
        self.assertEqual(df["Company"].iloc[0], "=x")


class TestAtomicToCsv(unittest.TestCase):
    def setUp(self):
        """
        Create an isolated temp directory for the write targets.
        """
        import shutil
        import tempfile
        from pathlib import Path

        self._tmp = Path(tempfile.mkdtemp(prefix="hft_atomic_"))
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)

    def test_writes_dataframe_round_trip(self):
        """
        The written CSV parses back to the same frame.
        """
        from app.utils.pd import atomic_to_csv

        df = pd.DataFrame({"A": ["1", "2"], "B": ["x", "y"]})
        target = self._tmp / "out.csv"

        atomic_to_csv(df, target, index=False)

        pd.testing.assert_frame_equal(pd.read_csv(target, dtype=str), df)

    def test_failure_leaves_target_intact_and_no_tmp_files(self):
        """
        A crash mid-write must neither truncate the existing file nor leave
        temp files behind — that is the whole point of the helper.
        """
        from app.utils.pd import atomic_to_csv

        target = self._tmp / "out.csv"
        target.write_text("original", encoding="utf-8")

        class _Boom:
            def to_csv(self, f, **kwargs):
                """
                Simulate a failure after a partial write.
                """
                f.write("partial")
                raise RuntimeError("disk full")

        with self.assertRaises(RuntimeError):
            atomic_to_csv(_Boom(), target, index=False)  # type: ignore[arg-type]

        self.assertEqual(target.read_text(encoding="utf-8"), "original")
        self.assertEqual([p.name for p in self._tmp.iterdir()], ["out.csv"])


if __name__ == "__main__":
    unittest.main()

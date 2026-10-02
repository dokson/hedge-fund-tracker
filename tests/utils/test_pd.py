import os
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


class TestAtomicWriteText(unittest.TestCase):
    def setUp(self):
        """
        Create an isolated temp directory for the write targets.
        """
        import shutil
        import tempfile
        from pathlib import Path

        self._tmp = Path(tempfile.mkdtemp(prefix="hft_atomic_txt_"))
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)

    def test_transient_replace_failure_is_retried(self):
        """
        A PermissionError from os.replace (a reader holds the target on Windows) is retried.
        """
        from unittest.mock import patch

        from app.utils.pd import atomic_write_text

        target = self._tmp / "out.txt"
        target.write_text("old", encoding="utf-8")
        real_replace = os.replace
        calls: list[int] = []

        def flaky_replace(src, dst):
            """
            Fail the first swap like a file open for reading, then swap for real.
            """
            calls.append(1)
            if len(calls) == 1:
                raise PermissionError("target in use")
            real_replace(src, dst)

        with (
            patch("app.utils.pd.os.replace", side_effect=flaky_replace),
            patch("app.utils.pd.time.sleep") as mock_sleep,
        ):
            atomic_write_text(target, "new")

        self.assertEqual(target.read_text(encoding="utf-8"), "new")
        self.assertEqual(len(calls), 2)
        mock_sleep.assert_called_once()
        self.assertEqual([p.name for p in self._tmp.iterdir()], ["out.txt"])

    def test_persistent_replace_failure_gives_up_and_cleans_up(self):
        """
        After a bounded number of attempts the error propagates and no temp file is left.
        """
        from unittest.mock import patch

        from app.utils.pd import atomic_write_text

        target = self._tmp / "out.txt"
        target.write_text("old", encoding="utf-8")

        with (
            patch("app.utils.pd.os.replace", side_effect=PermissionError("in use")) as mock_replace,
            patch("app.utils.pd.time.sleep"),
            self.assertRaises(PermissionError),
        ):
            atomic_write_text(target, "new")

        self.assertLessEqual(mock_replace.call_count, 10)
        self.assertGreater(mock_replace.call_count, 1)
        self.assertEqual(target.read_text(encoding="utf-8"), "old")
        self.assertEqual([p.name for p in self._tmp.iterdir()], ["out.txt"])

    def test_writes_text_and_leaves_no_tmp_files(self):
        """
        The target holds exactly the text written and no temp file survives.
        """
        from app.utils.pd import atomic_write_text

        target = self._tmp / "out.txt"
        target.write_text("old", encoding="utf-8")

        atomic_write_text(target, "a\nb\n")

        self.assertEqual(target.read_bytes(), b"a\nb\n")
        self.assertEqual([p.name for p in self._tmp.iterdir()], ["out.txt"])

    def test_preserves_the_existing_file_mode(self):
        """
        mkstemp creates 0600 files; replacing a 0644 file must not narrow its permissions.
        """
        import stat
        from unittest.mock import patch

        from app.utils.pd import atomic_write_text

        target = self._tmp / "out.txt"
        target.write_text("old", encoding="utf-8")
        mode = stat.S_IMODE(target.stat().st_mode)

        with patch("app.utils.pd.Path.chmod") as chmod:
            atomic_write_text(target, "new")

        chmod.assert_called_once()
        self.assertEqual(chmod.call_args.args[0], mode)

    def test_new_file_gets_world_readable_mode(self):
        """
        A file that did not exist yet is created 0644 rather than mkstemp's 0600.
        """
        from unittest.mock import patch

        from app.utils.pd import atomic_write_text

        with patch("app.utils.pd.Path.chmod") as chmod:
            atomic_write_text(self._tmp / "fresh.txt", "new")

        self.assertEqual(chmod.call_args.args[0], 0o644)

    def test_atomic_to_csv_preserves_the_existing_file_mode(self):
        """
        The CSV writer shares the same permission handling.
        """
        import stat
        from unittest.mock import patch

        from app.utils.pd import atomic_to_csv

        target = self._tmp / "out.csv"
        target.write_text("a\n1\n", encoding="utf-8")
        mode = stat.S_IMODE(target.stat().st_mode)

        with patch("app.utils.pd.Path.chmod") as chmod:
            atomic_to_csv(pd.DataFrame({"a": [2]}), target, index=False)

        self.assertEqual(chmod.call_args.args[0], mode)

    def test_failure_leaves_target_intact(self):
        """
        A failure before the swap keeps the original file and removes the temp file.
        """
        from unittest.mock import patch

        from app.utils.pd import atomic_write_text

        target = self._tmp / "out.txt"
        target.write_text("original", encoding="utf-8")

        with (
            patch("app.utils.pd.os.replace", side_effect=OSError("boom")),
            self.assertRaises(OSError),
        ):
            atomic_write_text(target, "new")

        self.assertEqual(target.read_text(encoding="utf-8"), "original")
        self.assertEqual([p.name for p in self._tmp.iterdir()], ["out.txt"])


class TestAtomicWriteRows(unittest.TestCase):
    def setUp(self):
        """
        Create an isolated temp directory for the write targets.
        """
        import shutil
        import tempfile
        from pathlib import Path

        self._tmp = Path(tempfile.mkdtemp(prefix="hft_atomic_rows_"))
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)

    def test_writes_rows_with_header_and_quoting(self):
        """
        Rows land under the header, fully quoted by default and minimally on request.
        """
        from app.utils.pd import atomic_write_rows

        target = self._tmp / "out.csv"
        atomic_write_rows(target, ["A", "B"], [{"A": "1", "B": "x"}])
        self.assertEqual(target.read_bytes(), b'"A","B"\r\n"1","x"\r\n')

        atomic_write_rows(target, ["A", "B"], [{"A": "1", "B": "x"}], quote_all=False)
        self.assertEqual(target.read_bytes(), b"A,B\r\n1,x\r\n")
        self.assertEqual([p.name for p in self._tmp.iterdir()], ["out.csv"])

    def test_preserves_the_existing_file_mode(self):
        """
        The row writer shares the permission handling of the other atomic writers.
        """
        import stat
        from unittest.mock import patch

        from app.utils.pd import atomic_write_rows

        target = self._tmp / "out.csv"
        target.write_text("A\n", encoding="utf-8")
        mode = stat.S_IMODE(target.stat().st_mode)

        with patch("app.utils.pd.Path.chmod") as chmod:
            atomic_write_rows(target, ["A"], [{"A": "1"}])

        self.assertEqual(chmod.call_args.args[0], mode)

    @unittest.skipIf(os.name == "nt", "POSIX permission bits")
    def test_does_not_narrow_a_0644_file(self):
        """
        mkstemp's 0600 must not leak onto a target that was 0644.
        """
        import stat

        from app.utils.pd import atomic_write_rows

        target = self._tmp / "out.csv"
        target.write_text("A\n", encoding="utf-8")
        target.chmod(0o644)

        atomic_write_rows(target, ["A"], [{"A": "1"}])

        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o644)


class TestEscapeCsvTextRows(unittest.TestCase):
    def test_escapes_company_and_industry_only(self):
        """
        Free-text fields are formula-escaped; identifiers and non-strings pass through.
        """
        from app.utils.pd import escape_csv_text_rows

        rows = [{"CUSIP": "=1", "Company": "=cmd", "Industry": "+x", "Shares": 5}]

        self.assertEqual(
            escape_csv_text_rows(rows),
            [{"CUSIP": "=1", "Company": "'=cmd", "Industry": "'+x", "Shares": 5}],
        )


if __name__ == "__main__":
    unittest.main()

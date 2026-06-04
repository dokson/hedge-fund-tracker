import unittest

from fastapi import HTTPException

from app.api.common import _require_cusip, _require_quarter, _require_ticker


class TestRequireQuarter(unittest.TestCase):
    """Validation for the quarter path/query parameter."""

    def test_accepts_valid_quarter(self):
        """A well-formed YYYYQ[1-4] string passes through unchanged."""
        self.assertEqual(_require_quarter("2024Q1"), "2024Q1")

    def test_rejects_bad_quarters(self):
        """Malformed, empty, or None quarters raise 422."""
        for bad in ["2024Q5", "24Q1", "2024", "", None, "2024q1"]:
            with self.subTest(value=bad), self.assertRaises(HTTPException) as ctx:
                _require_quarter(bad)
            self.assertEqual(ctx.exception.status_code, 422)


class TestRequireTicker(unittest.TestCase):
    """Validation/normalisation for the ticker parameter."""

    def test_normalises_to_upper(self):
        """A valid ticker is upper-cased."""
        self.assertEqual(_require_ticker("aapl"), "AAPL")
        self.assertEqual(_require_ticker("brk.b"), "BRK.B")

    def test_rejects_bad_tickers(self):
        """Empty, too-long, or illegal-character tickers raise 422."""
        for bad in ["", None, "TOOLONGTICKER", "ab$c"]:
            with self.subTest(value=bad), self.assertRaises(HTTPException) as ctx:
                _require_ticker(bad)
            self.assertEqual(ctx.exception.status_code, 422)


class TestRequireCusip(unittest.TestCase):
    """Validation/normalisation for the CUSIP parameter."""

    def test_accepts_and_uppercases_9_chars(self):
        """A 9-char alphanumeric CUSIP passes and is upper-cased."""
        self.assertEqual(_require_cusip("037833100"), "037833100")
        self.assertEqual(_require_cusip("abc123xyz"), "ABC123XYZ")

    def test_rejects_wrong_length_or_chars(self):
        """Wrong length or non-alphanumeric CUSIPs raise 422."""
        for bad in ["", None, "12345678", "1234567890", "12345-789"]:
            with self.subTest(value=bad), self.assertRaises(HTTPException) as ctx:
                _require_cusip(bad)
            self.assertEqual(ctx.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()

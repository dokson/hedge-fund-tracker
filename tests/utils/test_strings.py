import unittest
from datetime import UTC, datetime
from unittest.mock import patch

from app.utils.strings import (
    add_days_to_yyyymmdd,
    eastern_today,
    escape_csv_formula,
    format_percentage,
    format_string,
    format_value,
    get_next_yyyymmdd_day,
    get_numeric,
    get_percentage_formatter,
    get_percentage_number,
    get_previous_quarter,
    get_previous_quarter_end_date,
    get_price_formatter,
    get_quarter,
    get_quarter_date,
    get_signed_perc_formatter,
    get_string_formatter,
    get_value_formatter,
    isin_to_cusip,
    parse_quarter,
)


class TestEscapeCsvFormula(unittest.TestCase):
    """CSV/spreadsheet formula-injection escaping."""

    def test_escapes_formula_prefixes(self):
        """A value starting with a formula trigger is prefixed with a quote."""
        for payload in ("=1+1", "+1", "-cmd", "@SUM(A1)", '=HYPERLINK("x")'):
            with self.subTest(value=payload):
                self.assertEqual(escape_csv_formula(payload), "'" + payload)

    def test_leaves_normal_text_untouched(self):
        """Ordinary names (incl. digit-leading) and empty strings pass through."""
        for value in ("Acme Inc", "", "3X Industries", "Globex Corp"):
            with self.subTest(value=value):
                self.assertEqual(escape_csv_formula(value), value)


class TestStrings(unittest.TestCase):
    def test_format_percentage(self):
        """
        Tests the format_percentage function.
        """
        cases = [
            ((0.1,), {}, "0.1%"),
            ((0.02,), {}, "0%"),
            ((0.02,), {"decimal_places": 2}, "0.02%"),
            ((0.09,), {}, "0.1%"),
            ((0.09,), {"decimal_places": 2}, "0.09%"),
            ((0.009,), {}, "<.01%"),
            ((0.1234,), {}, "0.1%"),
            ((0.1234,), {"decimal_places": 2}, "0.12%"),
            ((0.1234,), {"decimal_places": 3}, "0.123%"),
            ((0.1234,), {"decimal_places": 4}, "0.1234%"),
            ((0.1234,), {"show_sign": True, "decimal_places": 2}, "+0.12%"),
            ((-0.1234,), {"show_sign": True, "decimal_places": 2}, "-0.12%"),
            ((1.2,), {"show_sign": True}, "+1.2%"),
            ((0.005,), {}, "<.01%"),
            ((9.87,), {}, "9.9%"),
            ((9.87,), {"decimal_places": 2}, "9.87%"),
            ((9.876,), {"decimal_places": 2}, "9.88%"),
            ((0.0,), {}, "0%"),
            ((0.0,), {"show_sign": True}, "+0%"),
            ((100,), {}, "100%"),
        ]
        for args, kwargs, expected in cases:
            with self.subTest(args=args, kwargs=kwargs):
                self.assertEqual(format_percentage(*args, **kwargs), expected)

    def test_format_value(self):
        """
        Tests the format_value function.
        """
        cases = [
            (210, "210"),
            (-210, "-210"),
            (1234, "1.23K"),
            (-1234, "-1.23K"),
            (1234567, "1.23M"),
            (-1234567, "-1.23M"),
            (9870123456, "9.87B"),
            (-9870123456, "-9.87B"),
            (9876543210, "9.88B"),
            (-9876543210, "-9.88B"),
            (1234567891011, "1.23T"),
            (-1234567891011, "-1.23T"),
            (9999999999999, "10T"),
            (-9999999999999, "-10T"),
        ]
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(format_value(value), expected)

    def test_get_numeric(self):
        """
        Tests the get_numeric function.
        """
        cases = [
            ("500", 500),
            ("-500", -500),
            ("1.23K", 1230),
            ("-1.23K", -1230),
            ("1.23M", 1230000),
            ("-1.23M", -1230000),
            ("9.87B", 9870000000),
            ("-9.87B", -9870000000),
            ("9.88B", 9880000000),
            ("-9.88B", -9880000000),
            ("1.23T", 1230000000000),
            ("-1.23T", -1230000000000),
            ("1.00M", 1000000),
            ("-1.00M", -1000000),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(get_numeric(raw), expected)

    def test_get_percentage_number(self):
        """
        Tests the get_percentage_number function.
        """
        cases = [
            ("12.3%", 12.3),
            ("100%", 100.0),
            ("<.01%", 0.0),
            ("5%", 5.0),
            (".5%", 0.5),
            ("-10.5%", -10.5),
            ("0%", 0.0),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(get_percentage_number(raw), expected)

    def test_get_quarter(self):
        """
        Tests the get_quarter function on quarter boundary dates.
        """
        cases = [
            ("2023-01-01", "2023Q1"),
            ("2023-03-31", "2023Q1"),
            ("2024-04-01", "2024Q2"),
            ("2024-06-30", "2024Q2"),
            ("2020-07-01", "2020Q3"),
            ("2020-09-30", "2020Q3"),
            ("2022-10-01", "2022Q4"),
            ("2022-12-31", "2022Q4"),
        ]
        for date, expected in cases:
            with self.subTest(date=date):
                self.assertEqual(get_quarter(date), expected)

    def test_parse_quarter(self):
        """
        Tests the parse_quarter function.
        """
        self.assertEqual(parse_quarter("2025Q1"), (2025, 1))
        self.assertEqual(parse_quarter("1999Q4"), (1999, 4))
        with self.assertRaises(ValueError):
            parse_quarter("2025Q5")
        with self.assertRaises(ValueError):
            parse_quarter("not_a_quarter")

    def test_get_previous_quarter(self):
        """
        Tests the get_previous_quarter function.
        """
        self.assertEqual(get_previous_quarter("2025Q2"), "2025Q1")
        self.assertEqual(get_previous_quarter("2025Q1"), "2024Q4")
        self.assertEqual(get_previous_quarter("2020Q1"), "2019Q4")

    def test_get_quarter_date(self):
        """
        Tests the get_quarter_date function.
        """
        cases = [
            ("2024Q1", "2024-03-31"),
            ("2025Q2", "2025-06-30"),
            ("2023Q3", "2023-09-30"),
            ("2021Q4", "2021-12-31"),
        ]
        for quarter, expected in cases:
            with self.subTest(quarter=quarter):
                self.assertEqual(get_quarter_date(quarter), expected)

    def test_get_previous_quarter_end_date(self):
        """
        Tests the get_previous_quarter_end_date function.
        """
        cases = [
            ("2024-05-15", "2024-03-31"),
            ("2024-02-10", "2023-12-31"),
            ("2024-01-01", "2023-12-31"),
        ]
        for date, expected in cases:
            with self.subTest(date=date):
                self.assertEqual(get_previous_quarter_end_date(date), expected)

    def test_isin_to_cusip(self):
        """
        Tests the isin_to_cusip function.
        """
        cases = [
            ("US0378331005", "037833100"),
            ("CA0000000000", "000000000"),
            ("CUSIP123", None),
            ("", None),
            (None, None),
        ]
        for isin, expected in cases:
            with self.subTest(isin=isin):
                self.assertEqual(isin_to_cusip(isin), expected)

    def test_format_string(self):
        """
        Tests the format_string function.
        """
        self.assertEqual(format_string("ETSY INC"), "Etsy Inc")
        self.assertEqual(format_string("NVIDIA Corporation"), "NVIDIA Corporation")
        self.assertEqual(format_string("GE HealthCare"), "GE HealthCare")
        self.assertEqual(format_string(""), "")
        self.assertEqual(format_string(None), None)
        # Leading/trailing whitespace is always stripped, regardless of case.
        self.assertEqual(
            format_string("ACME ENERGY INC COMMON STOCK  "), "Acme Energy Inc Common Stock"
        )
        self.assertEqual(format_string("  Mixed Case Co  "), "Mixed Case Co")
        # Internal runs of whitespace collapse to a single space.
        self.assertEqual(format_string("ETSY   INC"), "Etsy Inc")
        # A whitespace-only string normalises to empty, not None.
        self.assertEqual(format_string("   "), "")

    def test_add_days_to_yyyymmdd(self):
        """
        Tests add_days_to_yyyymmdd function.
        """
        self.assertEqual(add_days_to_yyyymmdd("20240101", 5), "20240106")
        self.assertEqual(add_days_to_yyyymmdd("20240228", 1), "20240229")  # Leap year
        self.assertEqual(add_days_to_yyyymmdd("20230228", 1), "20230301")  # Non leap year
        self.assertEqual(add_days_to_yyyymmdd("20240301", -2), "20240228")

    def test_get_next_yyyymmdd_day(self):
        """
        Tests get_next_yyyymmdd_day function.
        """
        self.assertEqual(get_next_yyyymmdd_day("20241231"), "20250101")
        self.assertEqual(get_next_yyyymmdd_day("20240228"), "20240229")

    def test_eastern_today_uses_eastern_not_utc(self):
        """
        At 02:00 UTC the US Eastern date is still the previous day; the helper
        must return the Eastern calendar date, not the local/UTC one, so SEC
        filing-date filters don't drift by a day.
        """
        utc_instant = datetime(2026, 3, 15, 2, 0, tzinfo=UTC)

        class _FixedDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return utc_instant.astimezone(tz)

        with patch("app.utils.strings.datetime", _FixedDatetime):
            result = eastern_today()

        self.assertEqual(result.strftime("%Y-%m-%d"), "2026-03-14")

    def test_formatter_factories(self):
        """Tests the various formatter factory functions."""
        self.assertEqual(get_percentage_formatter()(12.3456), "12.35%")
        self.assertEqual(get_price_formatter()(1234.5), "$1,234.50")
        self.assertEqual(get_price_formatter()(None), "N/A")
        self.assertEqual(get_signed_perc_formatter()(5.1), "+5.1%")
        self.assertEqual(get_signed_perc_formatter()(-3.2), "-3.2%")
        self.assertEqual(get_string_formatter(max_length=10)("SUPERLONGSTRING"), "Superlo...")
        self.assertEqual(get_value_formatter()(1_200_000), "1.2M")


if __name__ == "__main__":
    unittest.main()

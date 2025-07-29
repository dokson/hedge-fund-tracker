from scraper.string_utils import format_percentage, format_value, get_numeric, get_quarter

import unittest

class TestStringUtils(unittest.TestCase):

    def test_format_percentage(self):
        self.assertEqual(format_percentage(0.1234), "0.1%")
        self.assertEqual(format_percentage(0.1234, decimal_places=2), "0.12%")
        self.assertEqual(format_percentage(0.1234, show_sign=True), "+0.1%")
        self.assertEqual(format_percentage(0.1234, show_sign=True, decimal_places=2), "+0.12%")
        self.assertEqual(format_percentage(-0.1234, show_sign=True, decimal_places=2), "-0.12%")
        self.assertEqual(format_percentage(0.005), "<.01%")
        self.assertEqual(format_percentage(9.87), "9.9%")
        self.assertEqual(format_percentage(9.87, decimal_places=2), "9.87%")
        self.assertEqual(format_percentage(9.876, decimal_places=2), "9.88%")
        self.assertEqual(format_percentage(0.0), "0%")
        self.assertEqual(format_percentage(0.0, show_sign=True), "+0%")


    def test_format_value(self):
        self.assertEqual(format_value(210), "210")
        self.assertEqual(format_value(1234), "1.23K")
        self.assertEqual(format_value(1234567), "1.23M")
        self.assertEqual(format_value(9870123456), "9.87B")
        self.assertEqual(format_value(9876543210), "9.88B")
        self.assertEqual(format_value(1234567891011), "1.23T")
        self.assertEqual(format_value(9999999999999), "10T")


    def test_get_numeric(self):
        self.assertEqual(get_numeric("500"), 500)
        self.assertEqual(get_numeric("1.23K"), 1230)
        self.assertEqual(get_numeric("1.23M"), 1230000)
        self.assertEqual(get_numeric("9.87B"), 9870000000)
        self.assertEqual(get_numeric("9.88B"), 9880000000)
        self.assertEqual(get_numeric("1.23T"), 1230000000000)
        self.assertEqual(get_numeric("1.00M"), 1000000)

    def test_get_quarter(self):
        self.assertEqual(get_quarter("2023-03-15"), "2023Q1")
        self.assertEqual(get_quarter("2023-08-05"), "2023Q2")
        self.assertEqual(get_quarter("2023-09-30"), "2023Q3")
        self.assertEqual(get_quarter("2023-11-10"), "2023Q3")
        self.assertEqual(get_quarter("2024-01-15"), "2023Q4")
        self.assertEqual(get_quarter("2024-04-28"), "2024Q1")


if __name__ == '__main__':
    unittest.main()
from app.utils.strings import format_percentage, format_value, get_numeric, get_percentage_number, get_quarter, get_quarter_date
import unittest

class TestStrings(unittest.TestCase):

    def test_format_percentage(self):
        self.assertEqual(format_percentage(0.1), "0.1%")
        self.assertEqual(format_percentage(0.02), "0%")
        self.assertEqual(format_percentage(0.02, decimal_places=2), "0.02%")
        self.assertEqual(format_percentage(0.09), "0.1%")
        self.assertEqual(format_percentage(0.09, decimal_places=2), "0.09%")
        self.assertEqual(format_percentage(0.009), "<.01%")
        self.assertEqual(format_percentage(0.1234), "0.1%")
        self.assertEqual(format_percentage(0.1234, decimal_places=2), "0.12%")
        self.assertEqual(format_percentage(0.1234, decimal_places=3), "0.123%")
        self.assertEqual(format_percentage(0.1234, decimal_places=4), "0.1234%")
        self.assertEqual(format_percentage(0.1234, show_sign=True, decimal_places=2), "+0.12%")
        self.assertEqual(format_percentage(-0.1234, show_sign=True, decimal_places=2), "-0.12%")
        self.assertEqual(format_percentage(1.2, show_sign=True), "+1.2%")
        self.assertEqual(format_percentage(0.005), "<.01%")
        self.assertEqual(format_percentage(9.87), "9.9%")
        self.assertEqual(format_percentage(9.87, decimal_places=2), "9.87%")
        self.assertEqual(format_percentage(9.876, decimal_places=2), "9.88%")
        self.assertEqual(format_percentage(0.0), "0%")
        self.assertEqual(format_percentage(0.0, show_sign=True), "+0%")
        self.assertEqual(format_percentage(100), "100%")


    def test_format_value(self):
        self.assertEqual(format_value(210), "210")
        self.assertEqual(format_value(-210), "-210")
        self.assertEqual(format_value(1234), "1.23K")
        self.assertEqual(format_value(-1234), "-1.23K")
        self.assertEqual(format_value(1234567), "1.23M")
        self.assertEqual(format_value(-1234567), "-1.23M")
        self.assertEqual(format_value(9870123456), "9.87B")
        self.assertEqual(format_value(-9870123456), "-9.87B")
        self.assertEqual(format_value(9876543210), "9.88B")
        self.assertEqual(format_value(-9876543210), "-9.88B")
        self.assertEqual(format_value(1234567891011), "1.23T")
        self.assertEqual(format_value(-1234567891011), "-1.23T")
        self.assertEqual(format_value(9999999999999), "10T")
        self.assertEqual(format_value(-9999999999999), "-10T")


    def test_get_numeric(self):
        self.assertEqual(get_numeric("500"), 500)
        self.assertEqual(get_numeric("-500"), -500)
        self.assertEqual(get_numeric("1.23K"), 1230)
        self.assertEqual(get_numeric("-1.23K"), -1230)
        self.assertEqual(get_numeric("1.23M"), 1230000)
        self.assertEqual(get_numeric("-1.23M"), -1230000)
        self.assertEqual(get_numeric("9.87B"), 9870000000)
        self.assertEqual(get_numeric("-9.87B"), -9870000000)
        self.assertEqual(get_numeric("9.88B"), 9880000000)
        self.assertEqual(get_numeric("-9.88B"), -9880000000)
        self.assertEqual(get_numeric("1.23T"), 1230000000000)
        self.assertEqual(get_numeric("-1.23T"), -1230000000000)
        self.assertEqual(get_numeric("1.00M"), 1000000)
        self.assertEqual(get_numeric("-1.00M"), -1000000)

    
    def test_get_percentage_number(self):
        self.assertEqual(get_percentage_number("12.3%"), 12.3)
        self.assertEqual(get_percentage_number("100%"), 100.0)
        self.assertEqual(get_percentage_number("<.01%"), 0.0)
        self.assertEqual(get_percentage_number("5%"), 5.0)
        self.assertEqual(get_percentage_number(".5%"), 0.5)
        self.assertEqual(get_percentage_number("-10.5%"), -10.5)
        self.assertEqual(get_percentage_number("0%"), 0.0)


    def test_get_quarter(self):
        # Test Q1 boundaries
        self.assertEqual(get_quarter("2023-01-01"), "2023Q1")
        self.assertEqual(get_quarter("2023-03-31"), "2023Q1")
        # Test Q2 boundaries
        self.assertEqual(get_quarter("2024-04-01"), "2024Q2")
        self.assertEqual(get_quarter("2024-06-30"), "2024Q2")
        # Test Q3 boundaries
        self.assertEqual(get_quarter("2020-07-01"), "2020Q3")
        self.assertEqual(get_quarter("2020-09-30"), "2020Q3")
        # Test Q4 boundaries
        self.assertEqual(get_quarter("2022-10-01"), "2022Q4")
        self.assertEqual(get_quarter("2022-12-31"), "2022Q4")


    def test_get_quarter_date(self):
        self.assertEqual(get_quarter_date("2024Q1"), "2024-03-31")
        self.assertEqual(get_quarter_date("2025Q2"), "2025-06-30")
        self.assertEqual(get_quarter_date("2023Q3"), "2023-09-30")
        self.assertEqual(get_quarter_date("2021Q4"), "2021-12-31")


if __name__ == '__main__':
    unittest.main()
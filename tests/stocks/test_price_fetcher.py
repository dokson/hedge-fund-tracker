import unittest
from unittest.mock import patch
from datetime import date
from app.stocks.price_fetcher import PriceFetcher


class TestPriceFetcher(unittest.TestCase):

    # --- get_libraries ---

    def test_get_libraries_returns_yfinance_first(self):
        """
        Returns an ordered list where YFinance is the highest-priority library.
        """
        libraries = PriceFetcher.get_libraries()

        self.assertEqual(libraries[0].__name__, 'YFinance')

    def test_get_libraries_returns_tradingview_as_fallback(self):
        """
        Returns TradingView as the second (fallback) library.
        """
        libraries = PriceFetcher.get_libraries()

        self.assertEqual(len(libraries), 2)
        self.assertEqual(libraries[1].__name__, 'TradingView')

    # --- get_current_price ---

    @patch('app.stocks.price_fetcher.TradingView.get_current_price')
    @patch('app.stocks.price_fetcher.YFinance.get_current_price')
    def test_get_current_price_returns_price_from_first_library(self, mock_yf, mock_tv):
        """
        Returns the price from YFinance without calling TradingView if YFinance succeeds.
        """
        mock_yf.return_value = 150.25

        price = PriceFetcher.get_current_price('AAPL')

        self.assertEqual(price, 150.25)
        mock_tv.assert_not_called()

    @patch('app.stocks.price_fetcher.TradingView.get_current_price')
    @patch('app.stocks.price_fetcher.YFinance.get_current_price')
    def test_get_current_price_falls_back_when_first_returns_none(self, mock_yf, mock_tv):
        """
        Falls back to TradingView when YFinance returns None.
        """
        mock_yf.return_value = None
        mock_tv.return_value = 149.99

        price = PriceFetcher.get_current_price('AAPL')

        self.assertEqual(price, 149.99)

    @patch('app.stocks.price_fetcher.TradingView.get_current_price')
    @patch('app.stocks.price_fetcher.YFinance.get_current_price')
    def test_get_current_price_falls_back_when_first_raises(self, mock_yf, mock_tv):
        """
        Falls back to TradingView when YFinance raises an exception.
        """
        mock_yf.side_effect = Exception("API error")
        mock_tv.return_value = 149.99

        price = PriceFetcher.get_current_price('AAPL')

        self.assertEqual(price, 149.99)

    @patch('app.stocks.price_fetcher.TradingView.get_current_price')
    @patch('app.stocks.price_fetcher.YFinance.get_current_price')
    def test_get_current_price_returns_none_when_all_libraries_fail(self, mock_yf, mock_tv):
        """
        Returns None when all libraries fail to provide a price.
        """
        mock_yf.return_value = None
        mock_tv.return_value = None

        price = PriceFetcher.get_current_price('UNKNOWN')

        self.assertIsNone(price)

    @patch('app.stocks.price_fetcher.TradingView.get_current_price')
    @patch('app.stocks.price_fetcher.YFinance.get_current_price')
    def test_get_current_price_returns_none_when_all_libraries_raise(self, mock_yf, mock_tv):
        """
        Returns None (not an exception) when every library raises.
        """
        mock_yf.side_effect = Exception("API down")
        mock_tv.side_effect = Exception("Also down")

        price = PriceFetcher.get_current_price('AAPL')

        self.assertIsNone(price)

    @patch('app.stocks.price_fetcher.TradingView.get_current_price')
    @patch('app.stocks.price_fetcher.YFinance.get_current_price')
    def test_get_current_price_preserves_float_precision(self, mock_yf, mock_tv):
        """
        Returns the exact float value provided by the library without rounding.
        """
        mock_yf.return_value = 150.2549999999

        price = PriceFetcher.get_current_price('AAPL')

        self.assertEqual(price, 150.2549999999)

    # --- get_avg_price ---

    @patch('app.stocks.price_fetcher.TradingView.get_avg_price')
    @patch('app.stocks.price_fetcher.YFinance.get_avg_price')
    def test_get_avg_price_returns_price_from_first_library(self, mock_yf, mock_tv):
        """
        Returns the historical price from YFinance without calling TradingView.
        """
        mock_yf.return_value = 145.50

        price = PriceFetcher.get_avg_price('AAPL', date(2023, 12, 25))

        self.assertEqual(price, 145.50)
        mock_tv.assert_not_called()

    @patch('app.stocks.price_fetcher.TradingView.get_avg_price')
    @patch('app.stocks.price_fetcher.YFinance.get_avg_price')
    def test_get_avg_price_falls_back_when_first_returns_none(self, mock_yf, mock_tv):
        """
        Falls back to TradingView when YFinance returns None for the historical date.
        """
        mock_yf.return_value = None
        mock_tv.return_value = 145.25

        price = PriceFetcher.get_avg_price('AAPL', date(2023, 12, 25))

        self.assertEqual(price, 145.25)

    @patch('app.stocks.price_fetcher.TradingView.get_avg_price')
    @patch('app.stocks.price_fetcher.YFinance.get_avg_price')
    def test_get_avg_price_falls_back_when_first_raises(self, mock_yf, mock_tv):
        """
        Falls back to TradingView when YFinance raises (e.g. date out of range).
        """
        mock_yf.side_effect = Exception("Date not available")
        mock_tv.return_value = 145.25

        price = PriceFetcher.get_avg_price('AAPL', date(2023, 12, 25))

        self.assertEqual(price, 145.25)

    @patch('app.stocks.price_fetcher.TradingView.get_avg_price')
    @patch('app.stocks.price_fetcher.YFinance.get_avg_price')
    def test_get_avg_price_returns_none_when_all_libraries_fail(self, mock_yf, mock_tv):
        """
        Returns None when no library can provide the historical price.
        """
        mock_yf.return_value = None
        mock_tv.return_value = None

        price = PriceFetcher.get_avg_price('AAPL', date(2099, 12, 25))

        self.assertIsNone(price)

    @patch('app.stocks.price_fetcher.TradingView.get_avg_price')
    @patch('app.stocks.price_fetcher.YFinance.get_avg_price')
    def test_get_avg_price_treats_zero_as_valid_price(self, mock_yf, mock_tv):
        """
        Returns 0 as a valid price (not treated as falsy None), since the code uses `is not None`.
        """
        mock_yf.return_value = 0

        price = PriceFetcher.get_avg_price('AAPL', date(2023, 12, 25))

        self.assertEqual(price, 0)
        mock_tv.assert_not_called()


if __name__ == '__main__':
    unittest.main()

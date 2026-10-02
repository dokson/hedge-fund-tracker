import unittest
from datetime import date
from unittest.mock import patch

from prometheus_client import REGISTRY
from yfinance.exceptions import YFRateLimitError

from app.stocks.price_fetcher import PriceFetcher


class TestPriceFetcher(unittest.TestCase):
    # --- get_libraries ---

    def test_get_libraries_priority_order(self):
        """
        The fallback chain queries YFinance, then TradingView, Nasdaq and StockAnalysis.
        """
        names = [library.__name__ for library in PriceFetcher.get_libraries()]

        self.assertEqual(names, ["YFinance", "TradingView", "Nasdaq", "StockAnalysis"])

    # --- get_current_price ---

    @patch("app.stocks.price_fetcher.TradingView.get_current_price")
    @patch("app.stocks.price_fetcher.YFinance.get_current_price")
    def test_get_current_price_returns_price_from_first_library(self, mock_yf, mock_tv):
        """
        Returns the price from YFinance without calling TradingView if YFinance succeeds.
        """
        mock_yf.return_value = 150.25

        price = PriceFetcher.get_current_price("AAPL")

        self.assertEqual(price, 150.25)
        mock_tv.assert_not_called()

    @patch("app.stocks.price_fetcher.TradingView.get_current_price")
    @patch("app.stocks.price_fetcher.YFinance.get_current_price")
    def test_get_current_price_falls_back_when_first_returns_none(self, mock_yf, mock_tv):
        """
        Falls back to TradingView when YFinance returns None.
        """
        mock_yf.return_value = None
        mock_tv.return_value = 149.99

        price = PriceFetcher.get_current_price("AAPL")

        self.assertEqual(price, 149.99)

    @patch("app.stocks.price_fetcher.TradingView.get_current_price")
    @patch("app.stocks.price_fetcher.YFinance.get_current_price")
    def test_get_current_price_falls_back_when_first_raises(self, mock_yf, mock_tv):
        """
        Falls back to TradingView when YFinance raises an exception.
        """
        mock_yf.side_effect = Exception("API error")
        mock_tv.return_value = 149.99

        price = PriceFetcher.get_current_price("AAPL")

        self.assertEqual(price, 149.99)

    @patch("app.stocks.price_fetcher.TradingView.get_current_price")
    @patch("app.stocks.price_fetcher.YFinance.get_current_price")
    @patch("app.stocks.price_fetcher.StockAnalysis.get_current_price")
    @patch("app.stocks.price_fetcher.Nasdaq.get_current_price")
    def test_get_current_price_returns_none_when_all_libraries_raise(
        self, mock_nasdaq, mock_sa, mock_yf, mock_tv
    ):
        """
        Returns None (not an exception) when every library raises.
        """
        mock_yf.side_effect = Exception("API down")
        mock_tv.side_effect = Exception("Also down")
        mock_nasdaq.return_value = None
        mock_sa.return_value = None

        price = PriceFetcher.get_current_price("AAPL")

        self.assertIsNone(price)

    # --- get_avg_price ---

    @patch("app.stocks.price_fetcher.TradingView.get_avg_price")
    @patch("app.stocks.price_fetcher.YFinance.get_avg_price")
    def test_get_avg_price_returns_price_from_first_library(self, mock_yf, mock_tv):
        """
        Returns the historical price from YFinance without calling TradingView.
        """
        mock_yf.return_value = 145.50

        price = PriceFetcher.get_avg_price("AAPL", date(2023, 12, 25))

        self.assertEqual(price, 145.50)
        mock_tv.assert_not_called()

    @patch("app.stocks.price_fetcher.TradingView.get_avg_price")
    @patch("app.stocks.price_fetcher.YFinance.get_avg_price")
    def test_get_avg_price_falls_back_when_first_returns_none(self, mock_yf, mock_tv):
        """
        Falls back to TradingView when YFinance returns None for the historical date.
        """
        mock_yf.return_value = None
        mock_tv.return_value = 145.25

        price = PriceFetcher.get_avg_price("AAPL", date(2023, 12, 25))

        self.assertEqual(price, 145.25)

    @patch("app.stocks.price_fetcher.TradingView.get_avg_price")
    @patch("app.stocks.price_fetcher.YFinance.get_avg_price")
    def test_get_avg_price_falls_back_when_first_raises(self, mock_yf, mock_tv):
        """
        Falls back to TradingView when YFinance raises (e.g. date out of range).
        """
        mock_yf.side_effect = Exception("Date not available")
        mock_tv.return_value = 145.25

        price = PriceFetcher.get_avg_price("AAPL", date(2023, 12, 25))

        self.assertEqual(price, 145.25)

    @patch("app.stocks.price_fetcher.TradingView.get_avg_price")
    @patch("app.stocks.price_fetcher.YFinance.get_avg_price")
    @patch("app.stocks.price_fetcher.StockAnalysis.get_avg_price")
    @patch("app.stocks.price_fetcher.Nasdaq.get_avg_price")
    def test_get_avg_price_returns_none_when_all_libraries_fail(
        self, mock_nasdaq, mock_sa, mock_yf, mock_tv
    ):
        """
        Returns None when no library can provide the historical price.
        """
        mock_yf.return_value = None
        mock_tv.return_value = None
        mock_nasdaq.return_value = None
        mock_sa.return_value = None

        price = PriceFetcher.get_avg_price("AAPL", date(2099, 12, 25))

        self.assertIsNone(price)

    @patch("app.stocks.price_fetcher.TradingView.get_avg_price")
    @patch("app.stocks.price_fetcher.YFinance.get_avg_price")
    def test_get_avg_price_treats_zero_as_valid_price(self, mock_yf, mock_tv):
        """
        Returns 0 as a valid price (not treated as falsy None), since the code uses `is not None`.
        """
        mock_yf.return_value = 0

        price = PriceFetcher.get_avg_price("AAPL", date(2023, 12, 25))

        self.assertEqual(price, 0)
        mock_tv.assert_not_called()

    # --- get_history ---

    @patch("app.stocks.price_fetcher.TradingView.get_history")
    @patch("app.stocks.price_fetcher.YFinance.get_history")
    def test_get_history_returns_points_from_first_library(self, mock_yf, mock_tv):
        """
        Returns history from YFinance without calling TradingView when YFinance returns data.
        """
        points = [{"date": "2024-01-01", "close": 100.0}, {"date": "2024-02-01", "close": 110.0}]
        mock_yf.return_value = points

        result = PriceFetcher.get_history("AAPL", "5y")

        self.assertEqual(result, points)
        mock_tv.assert_not_called()

    @patch("app.stocks.price_fetcher.TradingView.get_history")
    @patch("app.stocks.price_fetcher.YFinance.get_history")
    def test_get_history_falls_back_when_first_returns_empty(self, mock_yf, mock_tv):
        """
        Falls back to TradingView when YFinance returns None or empty.
        """
        tv_points = [{"date": "2024-01-01", "close": 99.0}]
        mock_yf.return_value = None
        mock_tv.return_value = tv_points

        result = PriceFetcher.get_history("AAPL", "5y")

        self.assertEqual(result, tv_points)

    @patch("app.stocks.price_fetcher.TradingView.get_history")
    @patch("app.stocks.price_fetcher.YFinance.get_history")
    def test_get_history_returns_empty_list_when_all_libraries_fail(self, mock_yf, mock_tv):
        """
        Returns an empty list (not None) when every source fails.
        """
        mock_yf.return_value = None
        mock_tv.return_value = None

        result = PriceFetcher.get_history("UNKNOWN", "5y")

        self.assertEqual(result, [])

    @patch("app.stocks.price_fetcher.TradingView.get_last_price_in_range")
    @patch("app.stocks.price_fetcher.YFinance.get_last_price_in_range")
    def test_get_last_price_in_range_falls_back(self, mock_yf, mock_tv):
        """
        The range lookup walks the library chain until one returns a price.
        """
        mock_yf.return_value = None
        mock_tv.return_value = 12.5
        start, end = date(2025, 5, 15), date(2025, 8, 14)
        self.assertEqual(PriceFetcher.get_last_price_in_range("GONE", start, end), 12.5)
        mock_yf.assert_called_once_with("GONE", start, end)


def _sample(name: str, provider: str) -> float:
    """
    Current value of a per-provider price counter.
    """
    return REGISTRY.get_sample_value(name, {"provider": provider}) or 0.0


class TestPriceFetcherMetrics(unittest.TestCase):
    @patch("app.stocks.price_fetcher.TradingView.get_current_price", return_value=1.0)
    @patch("app.stocks.price_fetcher.YFinance.get_current_price")
    def test_provider_failure_is_counted(self, mock_yf, _mock_tv):
        """
        A provider raising increments its failure counter, not its rate-limit one.
        """
        mock_yf.side_effect = Exception("API down")
        failed = _sample("hft_price_lookup_failures_total", "YFinance")
        limited = _sample("hft_price_rate_limited_total", "YFinance")

        with self.assertLogs("app.stocks.price_fetcher", level="ERROR"):
            PriceFetcher.get_current_price("AAPL")

        self.assertEqual(_sample("hft_price_lookup_failures_total", "YFinance"), failed + 1)
        self.assertEqual(_sample("hft_price_rate_limited_total", "YFinance"), limited)

    @patch("app.stocks.price_fetcher.TradingView.get_history", return_value=[{"close": 1}])
    @patch("app.stocks.price_fetcher.YFinance.get_history")
    def test_rate_limit_is_counted_separately(self, mock_yf, _mock_tv):
        """
        A Yahoo rate limit increments both the failure and the rate-limit counters.
        """
        mock_yf.side_effect = YFRateLimitError()
        failed = _sample("hft_price_lookup_failures_total", "YFinance")
        limited = _sample("hft_price_rate_limited_total", "YFinance")

        with self.assertLogs("app.stocks.price_fetcher", level="ERROR"):
            PriceFetcher.get_history("AAPL")

        self.assertEqual(_sample("hft_price_lookup_failures_total", "YFinance"), failed + 1)
        self.assertEqual(_sample("hft_price_rate_limited_total", "YFinance"), limited + 1)

    @patch("time.sleep")
    @patch("app.stocks.libraries.yfinance.yf.download")
    def test_bulk_info_rate_limit_is_counted(self, mock_download, _sleep):
        """
        Every rate-limited attempt of the bulk sweep is counted before propagating.
        """
        from app.stocks.libraries.yfinance import YFinance

        mock_download.side_effect = YFRateLimitError()
        limited = _sample("hft_price_rate_limited_total", "YFinance")

        with (
            self.assertLogs("app.stocks.libraries.yfinance", level="WARNING"),
            self.assertRaises(YFRateLimitError),
        ):
            YFinance.get_stocks_info(["AAPL"])

        attempts = YFinance.get_stocks_info.retry.stop.max_attempt_number
        self.assertEqual(_sample("hft_price_rate_limited_total", "YFinance"), limited + attempts)


if __name__ == "__main__":
    unittest.main()

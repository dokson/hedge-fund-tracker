import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from app.stocks.libraries.stockanalysis import StockAnalysis


def _make_api_response(rows):
    """
    Creates a mock StockAnalysis API JSON response with the given rows.
    """
    return {"status": 200, "data": rows}


class TestStockAnalysisFetchHistory(unittest.TestCase):
    @patch("app.stocks.libraries.stockanalysis.requests.get")
    def test_returns_rows_from_api(self, mock_get):
        """
        Returns the raw rows list from a successful API response.
        """
        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_api_response(
            [{"t": "2025-07-16", "o": 392.53, "h": 395.0, "l": 374.3, "c": 374.3}]
        )
        mock_get.return_value = mock_resp

        rows = StockAnalysis._fetch_history("ANSS", "5Y", "Daily")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["c"], 374.3)

    @patch("app.stocks.libraries.stockanalysis.requests.get")
    def test_returns_empty_list_when_no_data(self, mock_get):
        """
        Returns an empty list when the API reports no data for an unknown ticker.
        """
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": 404, "data": None}
        mock_get.return_value = mock_resp

        rows = StockAnalysis._fetch_history("UNKNOWN", "5Y", "Daily")

        self.assertEqual(rows, [])

    @patch("app.stocks.libraries.stockanalysis.requests.get")
    def test_returns_empty_list_when_request_raises(self, mock_get):
        """
        Returns an empty list when the HTTP request raises an exception.
        """
        mock_get.side_effect = Exception("Network error")

        rows = StockAnalysis._fetch_history("ANSS", "5Y", "Daily")

        self.assertEqual(rows, [])


class TestStockAnalysisGetAvgPrice(unittest.TestCase):
    @patch("app.stocks.libraries.stockanalysis.StockAnalysis._fetch_history")
    def test_returns_high_low_avg_for_exact_date(self, mock_fetch):
        """
        Returns (high + low) / 2 for the row matching the requested date exactly.
        This is the delisted-ticker case (e.g. ANSS after the Synopsys acquisition):
        the source no longer serves new bars but still has the historical ones.
        """
        mock_fetch.return_value = [
            {"t": "2025-05-15", "o": 347.43, "h": 349.1, "l": 342.45, "c": 343.52},
            {"t": "2025-05-14", "o": 345.15, "h": 350.7, "l": 345.15, "c": 347.87},
        ]

        price = StockAnalysis.get_avg_price("ANSS", date(2025, 5, 15))

        self.assertEqual(price, round((349.1 + 342.45) / 2, 2))

    @patch("app.stocks.libraries.stockanalysis.StockAnalysis._fetch_history")
    def test_falls_back_to_last_trading_day_before_requested_date(self, mock_fetch):
        """
        Uses the most recent bar at or before a non-trading requested date (weekend/holiday).
        """
        mock_fetch.return_value = [
            {"t": "2025-05-14", "o": 345.15, "h": 350.7, "l": 345.15, "c": 347.87},
            {"t": "2025-05-13", "o": 344.62, "h": 348.91, "l": 344.62, "c": 347.08},
        ]

        price = StockAnalysis.get_avg_price("ANSS", date(2025, 5, 16))

        self.assertEqual(price, round((350.7 + 345.15) / 2, 2))

    @patch("app.stocks.libraries.stockanalysis.StockAnalysis._fetch_history")
    def test_returns_none_when_no_bar_at_or_before_date(self, mock_fetch):
        """
        Returns None when every row is after the requested date.
        """
        mock_fetch.return_value = [{"t": "2025-05-14", "o": 1, "h": 1, "l": 1, "c": 1}]

        price = StockAnalysis.get_avg_price("ANSS", date(2025, 1, 1))

        self.assertIsNone(price)

    @patch("app.stocks.libraries.stockanalysis.StockAnalysis._fetch_history")
    def test_returns_none_when_no_rows(self, mock_fetch):
        """
        Returns None when the API has no history at all for the ticker.
        """
        mock_fetch.return_value = []

        price = StockAnalysis.get_avg_price("UNKNOWN", date(2025, 5, 15))

        self.assertIsNone(price)


class TestStockAnalysisGetCurrentPrice(unittest.TestCase):
    @patch("app.stocks.libraries.stockanalysis.StockAnalysis._fetch_history")
    def test_returns_close_of_most_recent_row(self, mock_fetch):
        """
        Returns the close price of the most recent bar (rows are newest-first).
        """
        mock_fetch.return_value = [
            {"t": "2026-07-28", "o": 340.03, "h": 342.89, "l": 335.6, "c": 340.08},
            {"t": "2026-07-27", "o": 334.54, "h": 339.57, "l": 334.02, "c": 336.91},
        ]

        price = StockAnalysis.get_current_price("AAPL")

        self.assertEqual(price, 340.08)

    @patch("app.stocks.libraries.stockanalysis.StockAnalysis._fetch_history")
    def test_returns_none_when_no_rows(self, mock_fetch):
        """
        Returns None when the API has no data.
        """
        mock_fetch.return_value = []

        price = StockAnalysis.get_current_price("UNKNOWN")

        self.assertIsNone(price)


class TestStockAnalysisGetHistory(unittest.TestCase):
    @patch("app.stocks.libraries.stockanalysis.StockAnalysis._fetch_history")
    def test_returns_points_oldest_first(self, mock_fetch):
        """
        Reverses the API's newest-first rows into oldest-first {date, open, high, low, close} points.
        """
        mock_fetch.return_value = [
            {"t": "2025-05-15", "o": 347.43, "h": 349.1, "l": 342.45, "c": 343.52},
            {"t": "2025-05-14", "o": 345.15, "h": 350.7, "l": 345.15, "c": 347.87},
        ]

        points = StockAnalysis.get_history("ANSS", period="5y")

        assert points is not None
        self.assertEqual(len(points), 2)
        self.assertEqual(points[0]["date"], "2025-05-14")
        self.assertEqual(points[1]["date"], "2025-05-15")
        self.assertEqual(points[0]["close"], 347.87)

    @patch("app.stocks.libraries.stockanalysis.StockAnalysis._fetch_history")
    def test_returns_none_when_no_rows(self, mock_fetch):
        """
        Returns None when the API has no data, matching the FinanceLibrary contract.
        """
        mock_fetch.return_value = []

        points = StockAnalysis.get_history("UNKNOWN")

        self.assertIsNone(points)

    @patch("app.stocks.libraries.stockanalysis.StockAnalysis._fetch_history")
    def test_uses_range_and_period_mapped_from_requested_period(self, mock_fetch):
        """
        Maps the yfinance-style period string to the API's range/period query params.
        """
        mock_fetch.return_value = [{"t": "2020-01-01", "o": 1, "h": 1, "l": 1, "c": 1}]

        StockAnalysis.get_history("AAPL", period="10y")

        mock_fetch.assert_called_once_with("AAPL", "10Y", "Monthly")


class TestStockAnalysisUnsupported(unittest.TestCase):
    def test_get_ticker_returns_none(self):
        """
        CUSIP-to-ticker resolution is not supported by this source.
        """
        self.assertIsNone(StockAnalysis.get_ticker("123456789"))

    def test_get_company_returns_none(self):
        """
        CUSIP-to-company resolution is not supported by this source.
        """
        self.assertIsNone(StockAnalysis.get_company("123456789"))


if __name__ == "__main__":
    unittest.main()

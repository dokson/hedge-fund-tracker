import unittest
from unittest.mock import patch, MagicMock
from datetime import date
from app.stocks.libraries.nasdaq import Nasdaq


def _make_api_response(rows, total_records=None):
    """
    Creates a mock Nasdaq API JSON response with the given rows.
    """
    if total_records is None:
        total_records = len(rows)
    return {
        "data": {
            "symbol": "TEST",
            "totalRecords": total_records,
            "tradesTable": {
                "headers": {},
                "rows": rows,
            },
        },
        "status": {"rCode": 200},
    }


def _make_empty_response():
    """
    Creates a mock Nasdaq API response with no data.
    """
    return {"data": None, "status": {"rCode": 400}}


class TestNasdaqGetTicker(unittest.TestCase):

    def test_get_ticker_always_returns_none(self):
        """
        Nasdaq does not support CUSIP-to-ticker resolution; always returns None.
        """
        self.assertIsNone(Nasdaq.get_ticker("037833100"))


class TestNasdaqGetCompany(unittest.TestCase):

    def test_get_company_always_returns_none(self):
        """
        Nasdaq does not support company lookup; always returns None.
        """
        self.assertIsNone(Nasdaq.get_company("037833100"))


class TestNasdaqParsePrice(unittest.TestCase):

    def test_parses_plain_number(self):
        """
        Parses a simple numeric string.
        """
        self.assertEqual(Nasdaq._parse_price("10.23"), 10.23)

    def test_parses_dollar_sign_and_commas(self):
        """
        Strips $ prefix and comma separators from stock prices.
        """
        self.assertEqual(Nasdaq._parse_price("$1,234.56"), 1234.56)

    def test_returns_none_for_na(self):
        """
        Returns None for N/A values.
        """
        self.assertIsNone(Nasdaq._parse_price("N/A"))

    def test_returns_none_for_empty_string(self):
        """
        Returns None for empty strings.
        """
        self.assertIsNone(Nasdaq._parse_price(""))

    def test_returns_none_for_none(self):
        """
        Returns None when input is None.
        """
        self.assertIsNone(Nasdaq._parse_price(None))


class TestNasdaqFetchHistorical(unittest.TestCase):

    @patch("app.stocks.libraries.nasdaq.requests.get")
    def test_returns_matching_row_for_date(self, mock_get):
        """
        Returns the row matching the requested date.
        """
        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_api_response([
            {"date": "03/28/2026", "close": "10.50", "high": "10.50", "low": "10.50"},
            {"date": "03/27/2026", "close": "10.23", "high": "10.23", "low": "10.23"},
        ])
        mock_get.return_value = mock_resp

        row = Nasdaq._fetch_historical("FMSMX", date(2026, 3, 27))

        self.assertEqual(row["close"], "10.23")

    @patch("app.stocks.libraries.nasdaq.requests.get")
    def test_returns_none_when_date_not_in_rows(self, mock_get):
        """
        Returns None when the API returns data but not for the requested date.
        """
        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_api_response([
            {"date": "03/28/2026", "close": "10.50", "high": "10.50", "low": "10.50"},
        ])
        mock_get.return_value = mock_resp

        row = Nasdaq._fetch_historical("FMSMX", date(2026, 3, 27))

        self.assertIsNone(row)

    @patch("app.stocks.libraries.nasdaq.requests.get")
    def test_returns_none_when_api_returns_no_data(self, mock_get):
        """
        Returns None when the API returns a null data field.
        """
        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_empty_response()
        mock_get.return_value = mock_resp

        row = Nasdaq._fetch_historical("UNKNOWN", date(2026, 3, 27))

        self.assertIsNone(row)

    @patch("app.stocks.libraries.nasdaq.requests.get")
    def test_returns_none_when_request_raises(self, mock_get):
        """
        Returns None when the HTTP request raises an exception.
        """
        mock_get.side_effect = Exception("Network error")

        row = Nasdaq._fetch_historical("FMSMX", date(2026, 3, 27))

        self.assertIsNone(row)


class TestNasdaqGetAvgPrice(unittest.TestCase):

    @patch("app.stocks.libraries.nasdaq.Nasdaq._fetch_historical")
    def test_returns_close_for_mutual_fund(self, mock_fetch):
        """
        Returns the close (NAV) price when high == low (typical for mutual funds).
        """
        mock_fetch.return_value = {
            "date": "03/27/2026", "close": "10.23",
            "high": "10.23", "low": "10.23",
        }

        price = Nasdaq.get_avg_price("FMSMX", date(2026, 3, 27))

        self.assertEqual(price, 10.23)

    @patch("app.stocks.libraries.nasdaq.Nasdaq._fetch_historical")
    def test_returns_high_low_avg_for_stocks(self, mock_fetch):
        """
        Returns (high + low) / 2 when high != low.
        """
        mock_fetch.return_value = {
            "date": "03/27/2026", "close": "$248.80",
            "high": "$255.49", "low": "$248.07",
        }

        price = Nasdaq.get_avg_price("AAPL", date(2026, 3, 27))

        self.assertEqual(price, round((255.49 + 248.07) / 2, 2))

    @patch("app.stocks.libraries.nasdaq.Nasdaq._fetch_historical")
    def test_returns_none_when_no_data(self, mock_fetch):
        """
        Returns None when _fetch_historical returns None.
        """
        mock_fetch.return_value = None

        price = Nasdaq.get_avg_price("UNKNOWN", date(2026, 3, 27))

        self.assertIsNone(price)

    @patch("app.stocks.libraries.nasdaq.Nasdaq._fetch_historical")
    def test_returns_none_when_close_is_na(self, mock_fetch):
        """
        Returns None when all price fields are N/A.
        """
        mock_fetch.return_value = {
            "date": "03/27/2026", "close": "N/A",
            "high": "N/A", "low": "N/A",
        }

        price = Nasdaq.get_avg_price("UNKNOWN", date(2026, 3, 27))

        self.assertIsNone(price)


class TestNasdaqGetCurrentPrice(unittest.TestCase):

    @patch("app.stocks.libraries.nasdaq.requests.get")
    def test_returns_latest_close_price(self, mock_get):
        """
        Returns the close price from the most recent row.
        """
        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_api_response([
            {"date": "03/31/2026", "close": "10.22"},
        ])
        mock_get.return_value = mock_resp

        price = Nasdaq.get_current_price("FMSMX")

        self.assertEqual(price, 10.22)

    @patch("app.stocks.libraries.nasdaq.requests.get")
    def test_returns_none_when_no_data(self, mock_get):
        """
        Returns None when the API returns no data.
        """
        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_empty_response()
        mock_get.return_value = mock_resp

        price = Nasdaq.get_current_price("UNKNOWN")

        self.assertIsNone(price)

    @patch("app.stocks.libraries.nasdaq.requests.get")
    def test_returns_none_when_request_raises(self, mock_get):
        """
        Returns None when the HTTP request raises an exception.
        """
        mock_get.side_effect = Exception("Network error")

        price = Nasdaq.get_current_price("FMSMX")

        self.assertIsNone(price)

    @patch("app.stocks.libraries.nasdaq.requests.get")
    def test_strips_dollar_sign_from_stock_price(self, mock_get):
        """
        Correctly parses prices with $ prefix.
        """
        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_api_response([
            {"date": "03/31/2026", "close": "$248.80"},
        ])
        mock_get.return_value = mock_resp

        price = Nasdaq.get_current_price("AAPL")

        self.assertEqual(price, 248.80)


if __name__ == "__main__":
    unittest.main()

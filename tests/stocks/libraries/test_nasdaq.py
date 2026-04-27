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


class TestNasdaqGetSymbolChanges(unittest.TestCase):

    @patch("app.stocks.libraries.nasdaq.requests.get")
    def test_returns_list_of_old_new_ticker_pairs(self, mock_get):
        """
        Returns a list of dicts with oldSymbol, newSymbol, and companyName.
        """
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": {
                "symbolChangeHistoryTable": {
                    "rows": [
                        {"oldSymbol": "BITF", "newSymbol": "KEEL", "companyName": "Keel Infrastructure Corp."},
                        {"oldSymbol": "NBY", "newSymbol": "SDEV", "companyName": "Stablecoin Development Corp."},
                    ]
                }
            }
        }
        mock_get.return_value = mock_resp

        changes = Nasdaq.get_symbol_changes()

        self.assertEqual(len(changes), 2)
        self.assertEqual(changes[0]["oldSymbol"], "BITF")
        self.assertEqual(changes[0]["newSymbol"], "KEEL")
        self.assertEqual(changes[1]["oldSymbol"], "NBY")

    @patch("app.stocks.libraries.nasdaq.requests.get")
    def test_returns_empty_list_when_no_data(self, mock_get):
        """
        Returns an empty list when the API returns null data.
        """
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": None}
        mock_get.return_value = mock_resp

        changes = Nasdaq.get_symbol_changes()

        self.assertEqual(changes, [])

    @patch("app.stocks.libraries.nasdaq.requests.get")
    def test_returns_empty_list_when_request_fails(self, mock_get):
        """
        Returns an empty list when the HTTP request raises an exception.
        """
        mock_get.side_effect = Exception("Network error")

        changes = Nasdaq.get_symbol_changes()

        self.assertEqual(changes, [])

    @patch("app.stocks.libraries.nasdaq.requests.get")
    def test_calls_correct_api_endpoint(self, mock_get):
        """
        Calls the NASDAQ symbol change history API with correct URL and headers.
        """
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": {"symbolChangeHistoryTable": {"rows": []}}}
        mock_get.return_value = mock_resp

        Nasdaq.get_symbol_changes()

        mock_get.assert_called_once()
        call_url = mock_get.call_args[0][0]
        self.assertIn("symbolchangehistory", call_url)


if __name__ == "__main__":
    unittest.main()

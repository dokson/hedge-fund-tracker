import unittest
from unittest.mock import MagicMock, patch

from app.stocks.libraries.fmp import FMP


def _mock_response(status_code: int, payload):
    """
    Builds a requests.Response-like mock with the given status code and JSON payload.
    """
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = 200 <= status_code < 300
    resp.json.return_value = payload
    return resp


class TestFmpGetCusip(unittest.TestCase):
    @patch("app.stocks.libraries.fmp.requests.get")
    def test_returns_cusip_for_us_ticker(self, mock_get):
        """
        Returns the CUSIP from the profile payload for a US-listed equity.
        """
        mock_get.return_value = _mock_response(
            200,
            [{"symbol": "AAPL", "cusip": "037833100", "isin": "US0378331005"}],
        )

        with patch.object(FMP, "API_KEY", "test-key"):
            self.assertEqual(FMP.get_cusip("AAPL"), "037833100")

        params = mock_get.call_args.kwargs["params"]
        self.assertEqual(params["symbol"], "AAPL")
        self.assertEqual(params["apikey"], "test-key")

    @patch("app.stocks.libraries.fmp.requests.get")
    def test_returns_none_when_cusip_field_absent(self, mock_get):
        """
        Returns None for non-US securities where FMP omits the CUSIP field
        (ISIN may still be present but we do not use it).
        """
        mock_get.return_value = _mock_response(
            200,
            [{"symbol": "QTEX", "cusip": None, "isin": "IL0011715781"}],
        )

        with patch.object(FMP, "API_KEY", "test-key"):
            self.assertIsNone(FMP.get_cusip("QTEX"))

    @patch("app.stocks.libraries.fmp.requests.get")
    def test_returns_none_when_no_data(self, mock_get):
        """
        Returns None when the profile endpoint replies with an empty list.
        """
        mock_get.return_value = _mock_response(200, [])
        with patch.object(FMP, "API_KEY", "test-key"):
            self.assertIsNone(FMP.get_cusip("ZZZZ"))

    @patch("app.stocks.libraries.fmp.requests.get")
    def test_returns_none_without_api_key(self, mock_get):
        """
        Returns None and skips the HTTP call when FMP_API_KEY is unset.
        """
        with patch.object(FMP, "API_KEY", None):
            self.assertIsNone(FMP.get_cusip("AAPL"))
        mock_get.assert_not_called()

    @patch("app.stocks.libraries.fmp.requests.get")
    def test_returns_none_on_http_error(self, mock_get):
        """
        Returns None when the endpoint replies with a non-OK status (rate limit, 5xx, ...).
        """
        mock_get.return_value = _mock_response(429, {"Error Message": "rate limit"})
        with patch.object(FMP, "API_KEY", "test-key"):
            self.assertIsNone(FMP.get_cusip("AAPL"))


class TestFmpGetProfile(unittest.TestCase):
    @patch("app.stocks.libraries.fmp.requests.get")
    def test_returns_profile_fields_without_isin(self, mock_get):
        """
        Returns sector/industry/country alongside cusip; ISIN is intentionally omitted.
        """
        mock_get.return_value = _mock_response(
            200,
            [
                {
                    "symbol": "AAPL",
                    "cusip": "037833100",
                    "isin": "US0378331005",
                    "sector": "Technology",
                    "industry": "Consumer Electronics",
                    "country": "US",
                }
            ],
        )

        with patch.object(FMP, "API_KEY", "test-key"):
            profile = FMP.get_profile("AAPL")

        assert profile is not None
        self.assertEqual(
            profile,
            {
                "cusip": "037833100",
                "sector": "Technology",
                "industry": "Consumer Electronics",
                "country": "US",
            },
        )
        self.assertNotIn("isin", profile)

    @patch("app.stocks.libraries.fmp.requests.get")
    def test_returns_none_when_no_data(self, mock_get):
        """
        Returns None when the profile endpoint replies empty.
        """
        mock_get.return_value = _mock_response(200, [])
        with patch.object(FMP, "API_KEY", "test-key"):
            self.assertIsNone(FMP.get_profile("ZZZZ"))

    @patch("app.stocks.libraries.fmp.requests.get")
    def test_returns_none_without_api_key(self, mock_get):
        """
        Returns None without performing an HTTP call when FMP_API_KEY is unset.
        """
        with patch.object(FMP, "API_KEY", None):
            self.assertIsNone(FMP.get_profile("AAPL"))
        mock_get.assert_not_called()


if __name__ == "__main__":
    unittest.main()

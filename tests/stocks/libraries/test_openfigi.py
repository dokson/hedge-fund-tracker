import unittest
from unittest.mock import MagicMock, patch

from app.stocks.libraries.openfigi import OpenFIGI


def _mock_response(status_code: int, payload):
    """
    Builds a requests.Response-like mock with the given status code and JSON payload.
    """
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = payload
    resp.ok = 200 <= status_code < 300
    return resp


class TestOpenFIGI(unittest.TestCase):
    @patch("app.stocks.libraries.openfigi.requests.post")
    def test_get_ticker_by_cusip(self, mock_post):
        """
        Returns the ticker from the first Common Stock match.
        """
        mock_post.return_value = _mock_response(
            200,
            [{"data": [{"ticker": "TSLA", "name": "TESLA INC", "securityType": "Common Stock"}]}],
        )

        self.assertEqual(OpenFIGI.get_ticker("88160R101"), "TSLA")

        call_kwargs = mock_post.call_args.kwargs
        self.assertEqual(call_kwargs["json"], [{"idType": "ID_CUSIP", "idValue": "88160R101"}])

    @patch("app.stocks.libraries.openfigi.requests.post")
    def test_get_ticker_prefers_common_stock(self, mock_post):
        """
        When multiple matches are returned, prefers Common Stock over other types.
        """
        mock_post.return_value = _mock_response(
            200,
            [
                {
                    "data": [
                        {"ticker": "TSLA-WT", "securityType": "Warrant"},
                        {"ticker": "TSLA", "securityType": "Common Stock"},
                    ]
                }
            ],
        )

        self.assertEqual(OpenFIGI.get_ticker("88160R101"), "TSLA")

    @patch("app.stocks.libraries.openfigi.requests.post")
    def test_get_ticker_no_match(self, mock_post):
        """
        Returns None when OpenFIGI reports no matches.
        """
        mock_post.return_value = _mock_response(200, [{"warning": "No identifier found."}])
        self.assertIsNone(OpenFIGI.get_ticker("00000X000"))

    @patch("app.stocks.libraries.openfigi.requests.post")
    def test_get_company(self, mock_post):
        """
        Returns the company name, run through format_string.
        """
        mock_post.return_value = _mock_response(
            200,
            [{"data": [{"ticker": "TSLA", "name": "TESLA INC", "securityType": "Common Stock"}]}],
        )

        self.assertEqual(OpenFIGI.get_company("88160R101"), "Tesla Inc")

    @patch("app.stocks.libraries.openfigi.requests.post")
    def test_rate_limit_returns_none(self, mock_post):
        """
        On HTTP 429 (rate limit), logs and returns None instead of raising.
        """
        mock_post.return_value = _mock_response(429, {"message": "Too Many Requests"})
        self.assertIsNone(OpenFIGI.get_ticker("88160R101"))

    @patch("app.stocks.libraries.openfigi.requests.post")
    def test_http_error_returns_none(self, mock_post):
        """
        On non-OK HTTP responses (other than 429), returns None rather than raising.
        """
        mock_post.return_value = _mock_response(500, {"message": "Server Error"})
        self.assertIsNone(OpenFIGI.get_ticker("88160R101"))

    @patch("app.stocks.libraries.openfigi.requests.post")
    def test_sends_api_key_when_present(self, mock_post):
        """
        Sends the X-OPENFIGI-APIKEY header when OPENFIGI_API_KEY is set.
        """
        mock_post.return_value = _mock_response(
            200,
            [{"data": [{"ticker": "TSLA", "securityType": "Common Stock"}]}],
        )

        with patch.object(OpenFIGI, "API_KEY", "test-key"):
            OpenFIGI.get_ticker("88160R101")

        headers = mock_post.call_args.kwargs["headers"]
        self.assertEqual(headers.get("X-OPENFIGI-APIKEY"), "test-key")

    @patch("app.stocks.libraries.openfigi.requests.post")
    def test_omits_api_key_header_when_absent(self, mock_post):
        """
        Does not send the X-OPENFIGI-APIKEY header when no key is configured.
        """
        mock_post.return_value = _mock_response(
            200,
            [{"data": [{"ticker": "TSLA", "securityType": "Common Stock"}]}],
        )

        with patch.object(OpenFIGI, "API_KEY", None):
            OpenFIGI.get_ticker("88160R101")

        headers = mock_post.call_args.kwargs["headers"]
        self.assertNotIn("X-OPENFIGI-APIKEY", headers)


if __name__ == "__main__":
    unittest.main()

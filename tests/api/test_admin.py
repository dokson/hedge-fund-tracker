import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

# Importing ticker_changes also pulls in app.database (it imports from it), so
# the app.database.* patch targets below resolve regardless of suite ordering.
# NB: endpoints backed by the top-level `database.updater` package are NOT
# HTTP-tested here — under VS Code's `-s ./tests` discovery the `tests/database`
# subpackage shadows the repo-root `database` package, making that import
# unreachable. Those handlers are trivial delegators.
import app.stocks.ticker_changes  # noqa: F401
from app.server import app

client = TestClient(app)


class TestNonStringFieldsRejected(unittest.TestCase):
    """Ticker/CUSIP correction endpoints reject non-string fields with 422."""

    @patch("app.database.update_ticker_for_cusip")
    @patch("app.database.update_ticker")
    def test_null_or_number_fields_return_422(self, mock_update, mock_update_cusip):
        """
        A null, empty or numeric field is a client error, not an AttributeError 500.
        """
        cases = [
            ("/api/update-ticker", {"old_ticker": "", "new_ticker": "NEW"}),
            ("/api/update-ticker", {"old_ticker": None, "new_ticker": "NEW"}),
            ("/api/update-ticker", {"old_ticker": "OLD", "new_ticker": 7}),
            ("/api/update-ticker", {"old_ticker": "OLD", "new_ticker": "NEW", "new_company": 3}),
            ("/api/update-cusip-ticker", {"cusip": None, "new_ticker": "NEW"}),
            ("/api/update-cusip-ticker", {"cusip": 123456789, "new_ticker": "NEW"}),
            ("/api/update-cusip-ticker", {"cusip": "123456789", "new_ticker": ["X"]}),
        ]
        for path, body in cases:
            with self.subTest(path=path, body=body):
                resp = client.post(path, json=body)
                self.assertEqual(resp.status_code, 422)
        mock_update.assert_not_called()
        mock_update_cusip.assert_not_called()

    @patch("app.database.update_ticker")
    def test_null_company_is_treated_as_absent(self, mock_update):
        """
        An explicit null company keeps the stored name; a given one is forwarded.
        """
        for company in (None, "NewCo"):
            with self.subTest(company=company):
                mock_update.reset_mock()
                resp = client.post(
                    "/api/update-ticker",
                    json={"old_ticker": "old", "new_ticker": "new", "new_company": company},
                )
                self.assertEqual(resp.status_code, 200)
                mock_update.assert_called_once_with("OLD", "NEW", new_company=company)

    def test_non_object_body_returns_422(self):
        """
        A JSON array body is rejected with 422.
        """
        resp = client.post(
            "/api/update-ticker", content=b"[1]", headers={"Content-Type": "application/json"}
        )
        self.assertEqual(resp.status_code, 422)


if __name__ == "__main__":
    unittest.main()

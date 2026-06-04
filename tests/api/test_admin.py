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


class TestUpdateTickerEndpoint(unittest.TestCase):
    """/api/update-ticker wiring + validation."""

    @patch("app.database.update_ticker")
    def test_success_delegates_to_service(self, mock_update):
        """A valid request calls update_ticker with the normalised arguments."""
        resp = client.post(
            "/api/update-ticker",
            json={"old_ticker": "old", "new_ticker": "new", "new_company": "NewCo"},
        )
        self.assertEqual(resp.status_code, 200)
        mock_update.assert_called_once_with("OLD", "NEW", new_company="NewCo")

    def test_invalid_ticker_returns_422(self):
        """A malformed ticker is rejected before delegating."""
        resp = client.post(
            "/api/update-ticker",
            json={"old_ticker": "", "new_ticker": "NEW"},
        )
        self.assertEqual(resp.status_code, 422)


class TestDatabaseFetchEndpoint(unittest.TestCase):
    """/api/database/fetch input validation (runs before any heavy import)."""

    def test_unknown_type_returns_422(self):
        """An unknown fetch type is rejected with 422."""
        resp = client.post("/api/database/fetch", json={"type": "weird"})
        self.assertEqual(resp.status_code, 422)


class TestTickerChangeEndpoints(unittest.TestCase):
    """NASDAQ ticker-change detection endpoint."""

    @patch("app.stocks.ticker_changes.detect_applicable_ticker_changes")
    def test_detect_returns_service_payload(self, mock_detect):
        """The detect endpoint returns the service result verbatim."""
        mock_detect.return_value = {"total_changes": 0, "applicable": []}
        resp = client.get("/api/detect-ticker-changes")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"total_changes": 0, "applicable": []})


class TestFundsMissingQuartersEndpoint(unittest.TestCase):
    """/api/funds-missing-quarters wiring."""

    @patch("app.database.get_funds_missing_quarters")
    def test_no_gaps_message(self, mock_missing):
        """An empty gap map yields the all-clear message."""
        mock_missing.return_value = {}
        resp = client.post("/api/funds-missing-quarters")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["missing"], {})
        self.assertIn("complete quarter coverage", body["message"])


if __name__ == "__main__":
    unittest.main()

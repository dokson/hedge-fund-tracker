import unittest
from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient

from app.server import app

client = TestClient(app)


class TestQuarterEndpoints(unittest.TestCase):
    """Quarter discovery + per-quarter listing/analysis."""

    def test_list_quarters_returns_list(self):
        """The quarters endpoint returns a JSON list."""
        resp = client.get("/api/database/quarters")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_invalid_quarter_format_returns_422(self):
        """A malformed quarter is rejected with 422."""
        resp = client.get("/api/database/quarters/2024Q9")
        self.assertEqual(resp.status_code, 422)

    def test_missing_quarter_returns_404(self):
        """A well-formed but absent quarter returns 404."""
        resp = client.get("/api/database/quarters/1999Q1")
        self.assertEqual(resp.status_code, 404)

    @patch("app.analysis.stocks.quarter_analysis")
    def test_analysis_returns_records_for_existing_quarter(self, mock_analysis):
        """Analysis of an existing quarter returns JSON-safe records."""
        from app.database import get_all_quarters

        quarters = get_all_quarters()
        if not quarters:
            self.skipTest("no quarters in database")
        mock_analysis.return_value = pd.DataFrame({"Ticker": ["AAA"], "Score": [1.0]})

        resp = client.get(f"/api/database/quarters/{quarters[0]}/analysis")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [{"Ticker": "AAA", "Score": 1.0}])


class TestDatabaseFileServing(unittest.TestCase):
    """Raw file serving under /database."""

    def test_missing_file_returns_404(self):
        """A missing (but safely-named) file returns 404."""
        resp = client.get("/database/definitely_not_here_xyz.csv")
        self.assertEqual(resp.status_code, 404)


class TestStockHistoryEndpoint(unittest.TestCase):
    """/api/stocks/{ticker}/history validation + delegation."""

    def test_invalid_ticker_returns_400(self):
        """An over-long ticker is rejected with 400."""
        resp = client.get("/api/stocks/AAAAAAAAAAAAAAAAA/history")
        self.assertEqual(resp.status_code, 400)

    def test_invalid_range_returns_400(self):
        """An unsupported range is rejected with 400."""
        resp = client.get("/api/stocks/AAA/history", params={"range": "99y"})
        self.assertEqual(resp.status_code, 400)

    @patch("app.stocks.price_fetcher.PriceFetcher.get_history")
    def test_success_returns_points(self, mock_history):
        """A valid request returns the fetched price points."""
        mock_history.return_value = [{"date": "2024-01-01", "close": 1.0}]
        resp = client.get("/api/stocks/AAA/history", params={"range": "1y"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["ticker"], "AAA")
        self.assertEqual(body["points"], [{"date": "2024-01-01", "close": 1.0}])


if __name__ == "__main__":
    unittest.main()

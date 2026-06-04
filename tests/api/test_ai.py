import unittest
from unittest.mock import MagicMock, patch

import pandas as pd
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.ai import _build_ai_client
from app.server import app

client = TestClient(app)


class TestBuildAiClient(unittest.TestCase):
    """Provider → client-class resolution."""

    def test_unknown_provider_raises_400(self):
        """An unrecognised provider id is rejected with HTTP 400."""
        with self.assertRaises(HTTPException) as ctx:
            _build_ai_client("bogus", None)
        self.assertEqual(ctx.exception.status_code, 400)

    @patch("app.ai.clients.GroqClient")
    def test_known_provider_builds_with_model(self, mock_groq):
        """A known provider instantiates its client, passing the model through."""
        result = _build_ai_client("groq", None, "model-x")
        mock_groq.assert_called_once_with(model="model-x")
        self.assertIs(result, mock_groq.return_value)


class TestPromiseScoreEndpoint(unittest.TestCase):
    """/api/ai/promise-score wiring + validation."""

    @patch("app.ai.agent.AnalystAgent")
    @patch("app.api.ai._build_ai_client")
    def test_success_returns_json_safe_records(self, mock_build, mock_agent_cls):
        """A valid request returns the agent's scored list as JSON records."""
        mock_build.return_value = MagicMock()
        mock_agent_cls.return_value.generate_scored_list.return_value = pd.DataFrame(
            {"Ticker": ["AAA"], "Score": [9.0]}
        )

        resp = client.post(
            "/api/ai/promise-score",
            json={"quarter": "2024Q1", "provider_id": "groq", "model_id": "m"},
        )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [{"Ticker": "AAA", "Score": 9.0}])

    def test_invalid_quarter_returns_422(self):
        """A malformed quarter is rejected before any AI work."""
        resp = client.post(
            "/api/ai/promise-score",
            json={"quarter": "nope", "provider_id": "groq"},
        )
        self.assertEqual(resp.status_code, 422)


class TestDueDiligenceEndpoint(unittest.TestCase):
    """/api/ai/due-diligence wiring + validation."""

    @patch("app.ai.agent.AnalystAgent")
    @patch("app.api.ai._build_ai_client")
    def test_success_returns_agent_payload(self, mock_build, mock_agent_cls):
        """A valid request returns the agent's due-diligence dict."""
        mock_build.return_value = MagicMock()
        mock_agent_cls.return_value.run_stock_due_diligence.return_value = {"verdict": "buy"}

        resp = client.post(
            "/api/ai/due-diligence",
            json={"ticker": "AAA", "quarter": "2024Q1", "provider_id": "groq"},
        )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"verdict": "buy"})

    def test_invalid_ticker_returns_422(self):
        """A malformed ticker is rejected with 422."""
        resp = client.post(
            "/api/ai/due-diligence",
            json={"ticker": "$$$", "quarter": "2024Q1", "provider_id": "groq"},
        )
        self.assertEqual(resp.status_code, 422)


if __name__ == "__main__":
    unittest.main()

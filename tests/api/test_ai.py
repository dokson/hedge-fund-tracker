import unittest
from unittest.mock import MagicMock, patch

import pandas as pd
from fastapi import HTTPException
from fastapi.testclient import TestClient
from tenacity import RetryError, retry, stop_after_attempt

from app.ai.clients.base_client import InvalidAIResponseError
from app.api.ai import _build_ai_client
from app.api.common import limiter
from app.server import app

client = TestClient(app)


def _exhausted_retry_error() -> RetryError:
    """
    Produce the RetryError tenacity raises once every attempt returned an invalid response.
    """

    @retry(stop=stop_after_attempt(1))
    def _always_invalid():
        """
        Fail every attempt with an invalid AI response.
        """
        raise InvalidAIResponseError("AI response is missing 2 ticker(s)")

    try:
        _always_invalid()
    except RetryError as exc:
        return exc
    raise AssertionError("expected RetryError")


class TestBuildAiClient(unittest.TestCase):
    """Provider → client-class resolution."""

    def test_unknown_provider_raises_400(self):
        """An unrecognised provider id is rejected with HTTP 400."""
        with self.assertRaises(HTTPException) as ctx:
            _build_ai_client("bogus", None)
        self.assertEqual(ctx.exception.status_code, 400)

    @patch("app.ai.clients.GoogleAIClient")
    def test_retired_provider_falls_back_to_default(self, mock_google):
        """A stored config still naming a retired provider degrades, never crashes."""
        with self.assertLogs("app.api.ai", level="WARNING"):
            result = _build_ai_client("github", None, "microsoft/phi-4")
        # The retired provider's model id is dropped with it.
        mock_google.assert_called_once_with()
        self.assertIs(result, mock_google.return_value)

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

    @patch("app.ai.agent.AnalystAgent")
    @patch("app.api.ai._build_ai_client")
    def test_exhausted_retries_return_readable_502(self, mock_build, mock_agent_cls):
        """
        An AI that never returns a valid answer yields a 502 naming the last failure.
        """
        mock_build.return_value = MagicMock()
        mock_agent_cls.return_value.run_stock_due_diligence.side_effect = _exhausted_retry_error()

        resp = client.post(
            "/api/ai/due-diligence",
            json={"ticker": "AAA", "quarter": "2024Q1", "provider_id": "groq"},
        )

        self.assertEqual(resp.status_code, 502)
        self.assertIn("missing 2 ticker", resp.json()["detail"])
        self.assertNotIn("Future", resp.json()["detail"])


class TestPromiseScoreRateLimit(unittest.TestCase):
    """
    A Yahoo rate limit during ranking is reported as a failure, never as an empty success.
    """

    @patch("app.ai.agent.AnalystAgent")
    @patch("app.api.ai._build_ai_client")
    def test_rate_limit_returns_503(self, mock_build, mock_agent_cls):
        """
        The blocking endpoint maps the rate limit to 503 with a readable detail.
        """
        from yfinance.exceptions import YFRateLimitError

        mock_build.return_value = MagicMock()
        mock_agent_cls.return_value.generate_scored_list.side_effect = YFRateLimitError()

        resp = client.post(
            "/api/ai/promise-score", json={"quarter": "2024Q1", "provider_id": "groq"}
        )

        self.assertEqual(resp.status_code, 503)
        self.assertIn("rate limit", resp.json()["detail"].lower())


class _NoRateLimit(unittest.TestCase):
    """
    Disable the per-route limiter so request-heavy validation tests don't hit 429.
    """

    def setUp(self):
        """
        Switch the shared limiter off for the duration of the test.
        """
        limiter.enabled = False
        self.addCleanup(setattr, limiter, "enabled", True)


class TestTopNValidation(_NoRateLimit):
    """top_n is coerced to an int and bounded on both promise-score endpoints."""

    @patch("app.ai.agent.AnalystAgent")
    @patch("app.api.ai._build_ai_client")
    def test_invalid_top_n_returns_422(self, mock_build, mock_agent_cls):
        """
        Out-of-range, non-numeric, boolean and null values are rejected before any AI work.
        """
        for path in ("/api/ai/promise-score", "/api/ai/promise-score/stream"):
            for bad in (0, 51, -3, "abc", True, None, 2.5, [5]):
                with self.subTest(path=path, top_n=bad):
                    resp = client.post(
                        path, json={"quarter": "2024Q1", "provider_id": "groq", "top_n": bad}
                    )
                    self.assertEqual(resp.status_code, 422)
        mock_agent_cls.assert_not_called()

    @patch("app.ai.agent.AnalystAgent")
    @patch("app.api.ai._build_ai_client")
    def test_numeric_string_top_n_is_coerced(self, mock_build, mock_agent_cls):
        """
        A numeric string is accepted and passed to the agent as an int.
        """
        mock_build.return_value = MagicMock()
        mock_agent_cls.return_value.generate_scored_list.return_value = pd.DataFrame()

        resp = client.post(
            "/api/ai/promise-score",
            json={"quarter": "2024Q1", "provider_id": "groq", "top_n": "50"},
        )

        self.assertEqual(resp.status_code, 200)
        mock_agent_cls.return_value.generate_scored_list.assert_called_once_with(top_n=50)

    @patch("app.ai.agent.AnalystAgent")
    @patch("app.api.ai._build_ai_client")
    def test_missing_top_n_defaults_to_20(self, mock_build, mock_agent_cls):
        """
        Omitting top_n keeps the default of 20.
        """
        mock_build.return_value = MagicMock()
        mock_agent_cls.return_value.generate_scored_list.return_value = pd.DataFrame()

        client.post("/api/ai/promise-score", json={"quarter": "2024Q1", "provider_id": "groq"})

        mock_agent_cls.return_value.generate_scored_list.assert_called_once_with(top_n=20)


class TestRequestBody(_NoRateLimit):
    """The shared body parser rejects payloads that are not JSON objects."""

    def test_non_object_body_returns_422(self):
        """
        A JSON array or malformed JSON is a client error, not a 500.
        """
        for path in (
            "/api/ai/promise-score",
            "/api/ai/due-diligence",
            "/api/ai/promise-score/stream",
            "/api/ai/due-diligence/stream",
        ):
            for content in (b"[1, 2]", b"{not json"):
                with self.subTest(path=path, content=content):
                    resp = client.post(
                        path, content=content, headers={"Content-Type": "application/json"}
                    )
                    self.assertEqual(resp.status_code, 422)

    def test_non_string_ticker_returns_422(self):
        """
        A numeric ticker is a validation error, not an AttributeError 500.
        """
        resp = client.post(
            "/api/ai/due-diligence",
            json={"ticker": 5, "quarter": "2024Q1", "provider_id": "groq"},
        )
        self.assertEqual(resp.status_code, 422)


if __name__ == "__main__":
    unittest.main()

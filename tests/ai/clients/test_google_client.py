import unittest
from unittest.mock import MagicMock, patch

from google.genai import types
from google.genai.errors import ClientError, ServerError
from tenacity import RetryError

from app.ai.clients.google_client import GoogleAIClient


def _thinking_level_rejected() -> ClientError:
    """
    Builds the 400 error Gemini raises when a model doesn't support
    ``thinking_config`` (mirrors the actual API error message).
    """
    return ClientError(
        400,
        {"error": {"code": 400, "message": "Thinking level is not supported for this model."}},
    )


def _model_overloaded() -> ServerError:
    """
    Builds the 503 error Gemini raises when a model is under high demand
    (mirrors the actual API error message).
    """
    return ServerError(
        503,
        {
            "error": {
                "code": 503,
                "message": "This model is currently experiencing high demand.",
                "status": "UNAVAILABLE",
            }
        },
    )


class TestGoogleAIClient(unittest.TestCase):
    def setUp(self):
        # Patch genai.Client globally for the setup to avoid ValueError in CI
        self.patcher = patch("app.ai.clients.google_client.genai.Client")
        self.mock_genai_client = self.patcher.start()

        # Setup mock instance
        self.mock_instance = self.mock_genai_client.return_value
        self.mock_response = MagicMock()
        self.mock_response.text = "Mocked Gemini response"
        self.mock_instance.models.generate_content.return_value = self.mock_response

        GoogleAIClient._thinking_unsupported.clear()
        self.sleep_patcher = patch("time.sleep")
        self.sleep_patcher.start()
        self.client = GoogleAIClient(model="gemini-3.5-flash")

    def tearDown(self):
        self.patcher.stop()
        self.sleep_patcher.stop()

    def test_generate_content_invocation(self):
        prompt = "Hello, Gemini!"
        response = self.client.generate_content(prompt)

        # Assertions
        self.assertEqual(response, "Mocked Gemini response")
        self.mock_instance.models.generate_content.assert_called_once()
        call_kwargs = self.mock_instance.models.generate_content.call_args.kwargs
        self.assertEqual(call_kwargs["model"], "gemini-3.5-flash")
        self.assertEqual(call_kwargs["contents"], prompt)
        thinking_config = call_kwargs["config"].thinking_config
        self.assertEqual(thinking_config.thinking_level, types.ThinkingLevel.LOW)

        # Verify provider name in get_model_name
        self.assertEqual(self.client.get_model_name(), "google/gemini-3.5-flash")

    def test_retries_without_thinking_config_when_model_rejects_it(self):
        """
        Transparently retries without thinking_config when the model rejects
        it, so older/non-thinking Gemini models need no special-casing.
        """
        self.mock_instance.models.generate_content.side_effect = [
            _thinking_level_rejected(),
            self.mock_response,
        ]

        response = self.client.generate_content("Hello, Gemini!")

        self.assertEqual(response, "Mocked Gemini response")
        self.assertEqual(self.mock_instance.models.generate_content.call_count, 2)
        last_call_kwargs = self.mock_instance.models.generate_content.call_args.kwargs
        self.assertNotIn("config", last_call_kwargs)

    def test_skips_thinking_config_on_subsequent_calls_after_rejection(self):
        """
        Remembers a model's rejection of thinking_config across calls, so
        later requests to the same model don't pay for the failing round trip.
        """
        self.mock_instance.models.generate_content.side_effect = [
            _thinking_level_rejected(),
            self.mock_response,
            self.mock_response,
        ]

        self.client.generate_content("Hello!")
        self.client.generate_content("Hello again!")

        self.assertEqual(self.mock_instance.models.generate_content.call_count, 3)
        last_call_kwargs = self.mock_instance.models.generate_content.call_args.kwargs
        self.assertNotIn("config", last_call_kwargs)

    def test_falls_back_to_configured_model_when_primary_is_overloaded(self):
        """
        Transparently switches to FALLBACK_MODEL when the primary model
        returns a 503 (high demand), instead of exhausting retries on it.
        """
        self.mock_instance.models.generate_content.side_effect = [
            _model_overloaded(),
            self.mock_response,
        ]

        response = self.client.generate_content("Hello, Gemini!")

        self.assertEqual(response, "Mocked Gemini response")
        self.assertEqual(self.mock_instance.models.generate_content.call_count, 2)
        last_call_kwargs = self.mock_instance.models.generate_content.call_args.kwargs
        self.assertEqual(last_call_kwargs["model"], GoogleAIClient.FALLBACK_MODEL)
        # The client remembers the switch, so later calls / logging reflect it.
        self.assertEqual(self.client.get_model_name(), f"google/{GoogleAIClient.FALLBACK_MODEL}")

    def test_propagates_error_when_fallback_model_also_fails(self):
        """
        Raises (after exhausting the outer retry) when the fallback model
        fails too, instead of masking the failure.
        """
        self.mock_instance.models.generate_content.side_effect = _model_overloaded()

        with self.assertRaises(RetryError):
            self.client.generate_content("Hello, Gemini!")

    def test_does_not_fall_back_when_already_on_the_fallback_model(self):
        """
        Doesn't loop back onto itself when the fallback model is the one
        that's overloaded.
        """
        client = GoogleAIClient(model=GoogleAIClient.FALLBACK_MODEL)
        self.mock_instance.models.generate_content.side_effect = _model_overloaded()

        with self.assertRaises(RetryError):
            client.generate_content("Hello, Gemini!")

        # No fallback available, but the outer @retry still gets its attempts.
        self.assertEqual(self.mock_instance.models.generate_content.call_count, 3)


if __name__ == "__main__":
    unittest.main()

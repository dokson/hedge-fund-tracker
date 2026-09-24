import unittest
from unittest.mock import MagicMock, patch

import httpx
from google.genai import types
from google.genai.errors import ClientError, ServerError
from tenacity import RetryError

from app.ai.clients.base_client import AIClient, ReasoningLevel
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


def _chunk(text):
    """
    Builds one streamed Gemini chunk carrying ``text``.
    """
    return MagicMock(text=text)


def _failing_stream(exc: BaseException, *texts):
    """
    Yields chunks for ``texts`` and then raises ``exc`` mid-iteration.
    """
    for text in texts:
        yield _chunk(text)
    raise exc


def _assert_afc_disabled(case: unittest.TestCase, config) -> None:
    """
    google-genai >= 2.21 warns on every generate_content call unless AFC is
    disabled explicitly, so EVERY call must carry a config that disables it.
    """
    case.assertIsNotNone(config)
    case.assertIsNotNone(config.automatic_function_calling)
    case.assertTrue(config.automatic_function_calling.disable)


class TestGoogleAIClient(unittest.TestCase):
    def setUp(self):
        # Patch genai.Client globally for the setup to avoid ValueError in CI
        self.patcher = patch("app.ai.clients.google_client.genai.Client")
        self.mock_genai_client = self.patcher.start()

        # Setup mock instance
        self.mock_instance = self.mock_genai_client.return_value
        self.mock_response = MagicMock()
        self.mock_response.text = "Mocked Gemini response"
        self.mock_instance.models.generate_content_stream.return_value = [self.mock_response]

        AIClient._reasoning_unsupported.clear()
        self.sleep_patcher = patch("time.sleep")
        self.sleep_patcher.start()
        self.client = GoogleAIClient(model="gemini-3.5-flash")

    def tearDown(self):
        self.patcher.stop()
        self.sleep_patcher.stop()

    def test_client_configured_with_request_timeout(self):
        """
        A stalled Gemini call must eventually time out instead of emitting
        heartbeats forever (the OpenAI-compatible path caps at 90s — mirror it).
        """
        _, kwargs = self.mock_genai_client.call_args
        http_options = kwargs.get("http_options")
        self.assertIsNotNone(http_options)
        self.assertEqual(http_options.timeout, 90_000)

    def test_generate_content_invocation(self):
        prompt = "Hello, Gemini!"
        response = self.client.generate_content(prompt)

        # Assertions
        self.assertEqual(response, "Mocked Gemini response")
        self.mock_instance.models.generate_content_stream.assert_called_once()
        call_kwargs = self.mock_instance.models.generate_content_stream.call_args.kwargs
        self.assertEqual(call_kwargs["model"], "gemini-3.5-flash")
        self.assertEqual(call_kwargs["contents"], prompt)
        config = call_kwargs["config"]
        _assert_afc_disabled(self, config)
        self.assertEqual(config.thinking_config.thinking_level, types.ThinkingLevel.LOW)

        # Verify provider name in get_model_name
        self.assertEqual(self.client.get_model_name(), "google/gemini-3.5-flash")

    def test_retries_without_thinking_config_when_model_rejects_it(self):
        """
        Transparently retries without thinking_config when the model rejects
        it, so older/non-thinking Gemini models need no special-casing.
        """
        self.mock_instance.models.generate_content_stream.side_effect = [
            _thinking_level_rejected(),
            [self.mock_response],
        ]

        response = self.client.generate_content("Hello, Gemini!")

        self.assertEqual(response, "Mocked Gemini response")
        self.assertEqual(self.mock_instance.models.generate_content_stream.call_count, 2)
        last_call_kwargs = self.mock_instance.models.generate_content_stream.call_args.kwargs
        # The retry drops thinking_config but must keep the AFC-disabling config.
        last_config = last_call_kwargs["config"]
        _assert_afc_disabled(self, last_config)
        self.assertIsNone(last_config.thinking_config)

    def test_disables_automatic_function_calling_on_every_call(self):
        """
        Both the thinking attempt and the no-thinking retry must disable AFC,
        or google-genai logs its "direct use of AFC" warning on each call.
        """
        self.mock_instance.models.generate_content_stream.side_effect = [
            _thinking_level_rejected(),
            [self.mock_response],
        ]

        self.client.generate_content("Hello, Gemini!")

        calls = self.mock_instance.models.generate_content_stream.call_args_list
        self.assertEqual(len(calls), 2)
        for call in calls:
            _assert_afc_disabled(self, call.kwargs["config"])

    def test_skips_thinking_config_on_subsequent_calls_after_rejection(self):
        """
        Remembers a model's rejection of thinking_config across calls, so
        later requests to the same model don't pay for the failing round trip.
        """
        self.mock_instance.models.generate_content_stream.side_effect = [
            _thinking_level_rejected(),
            [self.mock_response],
            [self.mock_response],
        ]

        self.client.generate_content("Hello!")
        self.client.generate_content("Hello again!")

        self.assertEqual(self.mock_instance.models.generate_content_stream.call_count, 3)
        last_call_kwargs = self.mock_instance.models.generate_content_stream.call_args.kwargs
        last_config = last_call_kwargs["config"]
        _assert_afc_disabled(self, last_config)
        self.assertIsNone(last_config.thinking_config)

    def test_falls_back_to_configured_model_when_primary_is_overloaded(self):
        """
        Transparently switches to FALLBACK_MODEL when the primary model
        returns a 503 (high demand), instead of exhausting retries on it.
        """
        self.mock_instance.models.generate_content_stream.side_effect = [
            _model_overloaded(),
            [self.mock_response],
        ]

        response = self.client.generate_content("Hello, Gemini!")

        self.assertEqual(response, "Mocked Gemini response")
        self.assertEqual(self.mock_instance.models.generate_content_stream.call_count, 2)
        last_call_kwargs = self.mock_instance.models.generate_content_stream.call_args.kwargs
        self.assertEqual(last_call_kwargs["model"], GoogleAIClient.FALLBACK_MODEL)
        _assert_afc_disabled(self, last_call_kwargs["config"])
        # The fallback is per call: the configured model stays the one the caller chose.
        self.assertEqual(self.client.model, "gemini-3.5-flash")

    def test_completion_log_names_the_model_that_answered(self):
        """
        After a fallback the "response in" log must name the fallback model, not the primary.
        """
        self.mock_instance.models.generate_content_stream.side_effect = [
            _model_overloaded(),
            [self.mock_response],
        ]

        with self.assertLogs("app.ai.clients.base_client", level="INFO") as cm:
            self.client.generate_content("Hello, Gemini!")

        done = [r.getMessage() for r in cm.records if "response in" in r.getMessage()]
        self.assertEqual(len(done), 1)
        self.assertIn(f"google/{GoogleAIClient.FALLBACK_MODEL}", done[0])

    def test_completion_log_names_the_primary_model_without_fallback(self):
        """
        Without a fallback the log keeps naming the configured model.
        """
        with self.assertLogs("app.ai.clients.base_client", level="INFO") as cm:
            self.client.generate_content("Hello, Gemini!")

        done = [r.getMessage() for r in cm.records if "response in" in r.getMessage()]
        self.assertIn("google/gemini-3.5-flash", done[0])

    def test_fallback_is_not_sticky_across_calls(self):
        """
        After a fallback, the next call tries the configured primary model again.
        """
        self.mock_instance.models.generate_content_stream.side_effect = [
            _model_overloaded(),
            [self.mock_response],
            [self.mock_response],
        ]

        self.client.generate_content("first")
        self.client.generate_content("second")

        last_call_kwargs = self.mock_instance.models.generate_content_stream.call_args.kwargs
        self.assertEqual(last_call_kwargs["model"], "gemini-3.5-flash")

    def test_retries_transient_errors(self):
        """
        5xx responses, 429 rate limits and transport failures are retried until attempts run out.
        """
        transient = [
            ServerError(500, {"error": {"code": 500, "message": "internal"}}),
            ClientError(429, {"error": {"code": 429, "message": "quota"}}),
            httpx.ConnectError("refused"),
            httpx.ReadTimeout("slow"),
            TimeoutError("slow"),
        ]
        for exc in transient:
            with self.subTest(exc=type(exc).__name__):
                client = GoogleAIClient(model=GoogleAIClient.FALLBACK_MODEL)
                self.mock_instance.models.generate_content_stream.reset_mock()
                self.mock_instance.models.generate_content_stream.side_effect = exc
                with self.assertRaises(RetryError):
                    client.generate_content("Hello")
                self.assertEqual(self.mock_instance.models.generate_content_stream.call_count, 3)

    def test_does_not_retry_permanent_errors(self):
        """
        Auth failures, bad requests and missing models fail on the first attempt.
        """
        permanent = [
            ClientError(400, {"error": {"code": 400, "message": "bad request"}}),
            ClientError(401, {"error": {"code": 401, "message": "bad key"}}),
            ClientError(404, {"error": {"code": 404, "message": "no model"}}),
        ]
        for exc in permanent:
            with self.subTest(code=exc.code):
                self.mock_instance.models.generate_content_stream.reset_mock()
                self.mock_instance.models.generate_content_stream.side_effect = exc
                with self.assertRaises(ClientError):
                    self.client.generate_content("Hello")
                self.assertEqual(self.mock_instance.models.generate_content_stream.call_count, 1)

    def test_propagates_error_when_fallback_model_also_fails(self):
        """
        Raises (after exhausting the outer retry) when the fallback model
        fails too, instead of masking the failure.
        """
        self.mock_instance.models.generate_content_stream.side_effect = _model_overloaded()

        with self.assertRaises(RetryError):
            self.client.generate_content("Hello, Gemini!")

    def test_does_not_fall_back_when_already_on_the_fallback_model(self):
        """
        Doesn't loop back onto itself when the fallback model is the one
        that's overloaded.
        """
        client = GoogleAIClient(model=GoogleAIClient.FALLBACK_MODEL)
        self.mock_instance.models.generate_content_stream.side_effect = _model_overloaded()

        with self.assertRaises(RetryError):
            client.generate_content("Hello, Gemini!")

        # No fallback available, but the outer @retry still gets its attempts.
        self.assertEqual(self.mock_instance.models.generate_content_stream.call_count, 3)

    def test_requests_the_asked_thinking_level(self):
        """
        An explicit reasoning level maps to the matching Gemini ThinkingLevel.
        """
        cases: tuple[tuple[ReasoningLevel, types.ThinkingLevel], ...] = (
            ("medium", types.ThinkingLevel.MEDIUM),
            ("high", types.ThinkingLevel.HIGH),
            ("low", types.ThinkingLevel.LOW),
        )
        for level, expected in cases:
            with self.subTest(level=level):
                self.client.generate_content("Hello", reasoning=level)
                config = self.mock_instance.models.generate_content_stream.call_args.kwargs[
                    "config"
                ]
                self.assertEqual(config.thinking_config.thinking_level, expected)

    def test_thinking_fallback_works_with_non_default_level(self):
        """
        A model rejecting a MEDIUM thinking level is retried without thinking_config.
        """
        self.mock_instance.models.generate_content_stream.side_effect = [
            _thinking_level_rejected(),
            [self.mock_response],
        ]

        response = self.client.generate_content("Hello", reasoning="medium")

        self.assertEqual(response, "Mocked Gemini response")
        calls = self.mock_instance.models.generate_content_stream.call_args_list
        self.assertEqual(
            calls[0].kwargs["config"].thinking_config.thinking_level, types.ThinkingLevel.MEDIUM
        )
        self.assertIsNone(calls[1].kwargs["config"].thinking_config)

    def test_concatenates_streamed_chunks(self):
        """
        The response is the concatenation of every chunk's text.
        """
        self.mock_instance.models.generate_content_stream.return_value = [
            _chunk("Hello, "),
            _chunk("world"),
            _chunk("!"),
        ]

        self.assertEqual(self.client.generate_content("Hi"), "Hello, world!")

    def test_skips_empty_chunks(self):
        """
        Chunks without text (None or empty) contribute nothing.
        """
        self.mock_instance.models.generate_content_stream.return_value = [
            _chunk(None),
            _chunk("a"),
            _chunk(""),
            _chunk("b"),
        ]

        self.assertEqual(self.client.generate_content("Hi"), "ab")

    def test_falls_back_when_overload_surfaces_mid_stream(self):
        """
        A 503 raised while iterating the stream still switches to FALLBACK_MODEL.
        """
        self.mock_instance.models.generate_content_stream.side_effect = [
            _failing_stream(_model_overloaded(), "partial"),
            [self.mock_response],
        ]

        response = self.client.generate_content("Hello")

        self.assertEqual(response, "Mocked Gemini response")
        last_call_kwargs = self.mock_instance.models.generate_content_stream.call_args.kwargs
        self.assertEqual(last_call_kwargs["model"], GoogleAIClient.FALLBACK_MODEL)

    def test_retries_transient_error_raised_mid_stream(self):
        """
        A transport failure during iteration is retried by the outer tenacity loop.
        """
        client = GoogleAIClient(model=GoogleAIClient.FALLBACK_MODEL)
        self.mock_instance.models.generate_content_stream.side_effect = [
            _failing_stream(httpx.ReadTimeout("slow"), "partial"),
            [self.mock_response],
        ]

        self.assertEqual(client.generate_content("Hello"), "Mocked Gemini response")
        self.assertEqual(self.mock_instance.models.generate_content_stream.call_count, 2)

    def test_logs_time_to_first_token_once(self):
        """
        The first-token progress line is emitted once, on the first non-empty chunk.
        """
        self.mock_instance.models.generate_content_stream.return_value = [
            _chunk(None),
            _chunk("a"),
            _chunk("b"),
        ]

        with self.assertLogs("app.ai.clients.google_client", level="INFO") as cm:
            self.client.generate_content("Hi")

        first_token = [r for r in cm.records if "first token" in r.getMessage()]
        self.assertEqual(len(first_token), 1)
        self.assertIn("google/gemini-3.5-flash", first_token[0].getMessage())


class TestGoogleDefaultModels(unittest.TestCase):
    """
    Defaults must name models the Gemini API still serves.
    """

    def test_fallback_differs_from_the_default(self):
        """
        The overload fallback must differ from the default, or a 503 has nowhere to go.
        """
        self.assertNotEqual(GoogleAIClient.FALLBACK_MODEL, GoogleAIClient.DEFAULT_MODEL)

    def test_constructor_uses_the_default_model(self):
        """
        Omitting the model picks DEFAULT_MODEL.
        """
        with patch("app.ai.clients.google_client.genai.Client"):
            self.assertEqual(GoogleAIClient().model, GoogleAIClient.DEFAULT_MODEL)


if __name__ == "__main__":
    unittest.main()

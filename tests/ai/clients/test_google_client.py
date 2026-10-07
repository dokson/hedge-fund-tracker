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


def _rate_limited(message: str = "Quota exceeded.") -> ClientError:
    """
    Builds the 429 error Gemini raises when a request quota is spent.
    """
    return ClientError(
        429,
        {"error": {"code": 429, "message": message, "status": "RESOURCE_EXHAUSTED"}},
    )


def _response(text):
    """
    Builds a Gemini response carrying ``text``.
    """
    return MagicMock(text=text)


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
        self.mock_response = _response("Mocked Gemini response")
        self.generate = self.mock_instance.models.generate_content
        self.generate.return_value = self.mock_response

        AIClient._reasoning_unsupported.clear()
        GoogleAIClient._quota_exhausted_until.clear()
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
        self.generate.assert_called_once()
        call_kwargs = self.generate.call_args.kwargs
        self.assertEqual(call_kwargs["model"], "gemini-3.5-flash")
        self.assertEqual(call_kwargs["contents"], prompt)
        config = call_kwargs["config"]
        _assert_afc_disabled(self, config)
        self.assertEqual(config.thinking_config.thinking_level, types.ThinkingLevel.LOW)

        # Verify provider name in get_model_name
        self.assertEqual(self.client.get_model_name(), "google/gemini-3.5-flash")

    def test_answer_without_text_is_an_empty_string(self):
        """
        A blocked or empty answer carries no text; the caller gets "" rather than None.
        """
        self.generate.return_value = _response(None)

        self.assertEqual(self.client.generate_content("Hi"), "")

    def test_retries_without_thinking_config_when_model_rejects_it(self):
        """
        Transparently retries without thinking_config when the model rejects
        it, so older/non-thinking Gemini models need no special-casing.
        """
        self.generate.side_effect = [_thinking_level_rejected(), self.mock_response]

        response = self.client.generate_content("Hello, Gemini!")

        self.assertEqual(response, "Mocked Gemini response")
        calls = self.generate.call_args_list
        self.assertEqual(len(calls), 2)
        # The retry drops thinking_config, but both attempts must disable AFC.
        for call in calls:
            _assert_afc_disabled(self, call.kwargs["config"])
        self.assertIsNone(calls[1].kwargs["config"].thinking_config)

    def test_skips_thinking_config_on_subsequent_calls_after_rejection(self):
        """
        Remembers a model's rejection of thinking_config across calls, so
        later requests to the same model don't pay for the failing round trip.
        """
        self.generate.side_effect = [
            _thinking_level_rejected(),
            self.mock_response,
            self.mock_response,
        ]

        self.client.generate_content("Hello!")
        self.client.generate_content("Hello again!")

        self.assertEqual(self.generate.call_count, 3)
        last_config = self.generate.call_args.kwargs["config"]
        _assert_afc_disabled(self, last_config)
        self.assertIsNone(last_config.thinking_config)

    def test_falls_back_to_configured_model_when_primary_is_overloaded(self):
        """
        Transparently switches to FALLBACK_MODEL when the primary model
        returns a 503 (high demand), instead of exhausting retries on it.
        """
        self.generate.side_effect = [_model_overloaded(), self.mock_response]

        response = self.client.generate_content("Hello, Gemini!")

        self.assertEqual(response, "Mocked Gemini response")
        self.assertEqual(self.generate.call_count, 2)
        last_call_kwargs = self.generate.call_args.kwargs
        self.assertEqual(last_call_kwargs["model"], GoogleAIClient.FALLBACK_MODEL)
        _assert_afc_disabled(self, last_call_kwargs["config"])
        # The fallback is per call: the configured model stays the one the caller chose.
        self.assertEqual(self.client.model, "gemini-3.5-flash")

    def test_completion_log_names_the_model_that_answered(self):
        """
        After a fallback the "response in" log must name the fallback model, not the primary.
        """
        self.generate.side_effect = [_model_overloaded(), self.mock_response]

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
        self.generate.side_effect = [_model_overloaded(), self.mock_response, self.mock_response]

        self.client.generate_content("first")
        self.client.generate_content("second")

        self.assertEqual(self.generate.call_args.kwargs["model"], "gemini-3.5-flash")

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
                self.generate.reset_mock()
                self.generate.side_effect = exc
                with self.assertRaises(RetryError):
                    client.generate_content("Hello")
                self.assertEqual(self.generate.call_count, 3)

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
                self.generate.reset_mock()
                self.generate.side_effect = exc
                with self.assertRaises(ClientError):
                    self.client.generate_content("Hello")
                self.assertEqual(self.generate.call_count, 1)

    def test_propagates_error_when_fallback_model_also_fails(self):
        """
        Raises (after exhausting the outer retry) when the fallback model
        fails too, instead of masking the failure.
        """
        self.generate.side_effect = _model_overloaded()

        with self.assertRaises(RetryError):
            self.client.generate_content("Hello, Gemini!")

    def test_does_not_fall_back_when_already_on_the_fallback_model(self):
        """
        Doesn't loop back onto itself when the fallback model is the one
        that's overloaded.
        """
        client = GoogleAIClient(model=GoogleAIClient.FALLBACK_MODEL)
        self.generate.side_effect = _model_overloaded()

        with self.assertRaises(RetryError):
            client.generate_content("Hello, Gemini!")

        # No fallback available, but the outer @retry still gets its attempts.
        self.assertEqual(self.generate.call_count, 3)

    def test_skips_a_primary_whose_quota_returns_in_hours(self):
        """
        A 429 saying the quota comes back in hours (a spent daily quota) sends the following
        calls straight to the fallback model instead of spending a request on the primary.
        """
        self.generate.side_effect = [
            _rate_limited("Quota exceeded. Please retry in 9h2m2.39s."),
            self.mock_response,
            self.mock_response,
        ]

        self.client.generate_content("first")
        self.client.generate_content("second")

        models = [c.kwargs["model"] for c in self.generate.call_args_list]
        self.assertEqual(
            models,
            ["gemini-3.5-flash", GoogleAIClient.FALLBACK_MODEL] * 1
            + [GoogleAIClient.FALLBACK_MODEL],
        )

    def test_spent_quota_is_shared_per_key_across_clients(self):
        """
        A new client on the same API key knows the daily quota is spent; another key does not.
        """
        self.generate.side_effect = [
            _rate_limited("Quota exceeded. Please retry in 9h2m2.39s."),
            self.mock_response,
            self.mock_response,
            self.mock_response,
        ]
        GoogleAIClient(model="gemini-3.5-flash", api_key="key-a").generate_content("first")
        GoogleAIClient(model="gemini-3.5-flash", api_key="key-a").generate_content("same key")
        GoogleAIClient(model="gemini-3.5-flash", api_key="key-b").generate_content("other key")

        models = [c.kwargs["model"] for c in self.generate.call_args_list]
        self.assertEqual(
            models,
            ["gemini-3.5-flash", GoogleAIClient.FALLBACK_MODEL]
            + [GoogleAIClient.FALLBACK_MODEL]
            + ["gemini-3.5-flash"],
        )

    def test_keeps_trying_a_primary_that_is_only_briefly_rate_limited(self):
        """
        A per-minute 429 (retry in seconds) must not sideline the primary model.
        """
        self.generate.side_effect = [
            _rate_limited("Quota exceeded. Please retry in 20.5s."),
            self.mock_response,
            self.mock_response,
        ]

        self.client.generate_content("first")
        self.client.generate_content("second")

        models = [c.kwargs["model"] for c in self.generate.call_args_list]
        self.assertEqual(
            models, ["gemini-3.5-flash", GoogleAIClient.FALLBACK_MODEL, "gemini-3.5-flash"]
        )

    def test_tries_the_primary_again_once_its_quota_has_reset(self):
        """
        The skip lasts as long as the quota takes to return, no longer.
        """
        self.generate.side_effect = [
            _rate_limited("Quota exceeded. Please retry in 9h0m0s."),
            self.mock_response,
            self.mock_response,
        ]

        with patch("app.ai.clients.google_client.time.monotonic", return_value=1000.0):
            self.client.generate_content("first")
        with patch(
            "app.ai.clients.google_client.time.monotonic", return_value=1000.0 + 9 * 3600 + 60
        ):
            self.client.generate_content("second")

        models = [c.kwargs["model"] for c in self.generate.call_args_list]
        self.assertEqual(
            models, ["gemini-3.5-flash", GoogleAIClient.FALLBACK_MODEL, "gemini-3.5-flash"]
        )

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
                config = self.generate.call_args.kwargs["config"]
                self.assertEqual(config.thinking_config.thinking_level, expected)

    def test_thinking_fallback_works_with_non_default_level(self):
        """
        A model rejecting a MEDIUM thinking level is retried without thinking_config.
        """
        self.generate.side_effect = [_thinking_level_rejected(), self.mock_response]

        response = self.client.generate_content("Hello", reasoning="medium")

        self.assertEqual(response, "Mocked Gemini response")
        calls = self.generate.call_args_list
        self.assertEqual(
            calls[0].kwargs["config"].thinking_config.thinking_level, types.ThinkingLevel.MEDIUM
        )
        self.assertIsNone(calls[1].kwargs["config"].thinking_config)

    def test_falls_back_when_primary_is_rate_limited(self):
        """
        A 429 on the primary model is answered by FALLBACK_MODEL in the same call, with no wait.
        """
        self.generate.side_effect = [_rate_limited(), self.mock_response]

        with patch("tenacity.nap.time.sleep") as nap:
            response = self.client.generate_content("Hello")

        self.assertEqual(response, "Mocked Gemini response")
        self.assertEqual(self.generate.call_count, 2)
        self.assertEqual(self.generate.call_args.kwargs["model"], GoogleAIClient.FALLBACK_MODEL)
        nap.assert_not_called()
        self.assertEqual(self.client.model, "gemini-3.5-flash")

    def test_falls_back_when_primary_stalls_past_the_timeout(self):
        """
        A primary model that never answers (read timeout) is answered by FALLBACK_MODEL in the
        same call, without waiting out a retry on the model that just stalled.
        """
        self.generate.side_effect = [httpx.ReadTimeout("no answer"), self.mock_response]

        with patch("tenacity.nap.time.sleep") as nap:
            response = self.client.generate_content("Hello")

        self.assertEqual(response, "Mocked Gemini response")
        self.assertEqual(self.generate.call_count, 2)
        self.assertEqual(self.generate.call_args.kwargs["model"], GoogleAIClient.FALLBACK_MODEL)
        nap.assert_not_called()
        self.assertEqual(self.client.model, "gemini-3.5-flash")

    def test_rate_limit_on_fallback_model_propagates_to_retry(self):
        """
        A 429 on the fallback model itself is left to the outer retry, which then gives up.
        """
        self.generate.side_effect = _rate_limited()

        with self.assertRaises(RetryError):
            self.client.generate_content("Hello")

        models = [c.kwargs["model"] for c in self.generate.call_args_list]
        self.assertEqual(models, ["gemini-3.5-flash", GoogleAIClient.FALLBACK_MODEL] * 3)


_SCHEMA = {
    "type": "object",
    "properties": {"a": {"type": "integer"}},
    "required": ["a"],
    "additionalProperties": False,
}


def _json_schema_rejected() -> ClientError:
    """
    Builds the 400 error Gemini raises when a model doesn't accept a JSON schema.
    """
    return ClientError(
        400,
        {
            "error": {
                "code": 400,
                "message": "response_json_schema is not supported for this model.",
                "status": "INVALID_ARGUMENT",
            }
        },
    )


class TestGoogleStructuredOutput(unittest.TestCase):
    """
    ``response_schema`` maps to Gemini's JSON mime type and JSON schema fields.
    """

    def setUp(self):
        """
        Patches the genai client and sleep, and clears the shared rejection memories.
        """
        patcher = patch("app.ai.clients.google_client.genai.Client")
        self.generate = patcher.start().return_value.models.generate_content
        self.addCleanup(patcher.stop)
        sleep_patcher = patch("time.sleep")
        sleep_patcher.start()
        self.addCleanup(sleep_patcher.stop)
        self.generate.return_value = _response('{"a": 1}')
        AIClient._reasoning_unsupported.clear()
        AIClient._structured_rejected.clear()
        self.addCleanup(AIClient._structured_rejected.clear)
        self.client = GoogleAIClient(model="gemini-3.5-flash")

    def configs(self) -> list:
        """
        The config of every request sent, in order.
        """
        return [c.kwargs["config"] for c in self.generate.call_args_list]

    def test_schema_mode_sets_mime_type_and_json_schema(self):
        """
        The strongest mode has Gemini enforce the schema.
        """
        self.client.generate_content("p", response_schema=_SCHEMA)
        config = self.configs()[0]
        self.assertEqual(config.response_mime_type, "application/json")
        self.assertEqual(config.response_json_schema, _SCHEMA)
        _assert_afc_disabled(self, config)
        self.assertEqual(self.client.last_structured_mode, "schema")

    def test_no_schema_leaves_the_config_plain(self):
        """
        Plain-text requests carry neither field.
        """
        self.client.generate_content("p")
        config = self.configs()[0]
        self.assertIsNone(config.response_mime_type)
        self.assertIsNone(config.response_json_schema)

    def test_rejected_schema_degrades_to_json_mode(self):
        """
        JSON mode keeps the mime type but drops the schema, which moves to the prompt.
        """
        self.generate.side_effect = [_json_schema_rejected(), _response("{}")]
        self.client.generate_content("p", response_schema=_SCHEMA)
        config = self.configs()[1]
        self.assertEqual(config.response_mime_type, "application/json")
        self.assertIsNone(config.response_json_schema)
        self.assertIn('"additionalProperties": false', self.generate.call_args.kwargs["contents"])
        self.assertEqual(self.client.last_structured_mode, "json")

    def test_thinking_rejection_is_not_a_structured_rejection(self):
        """
        Each fallback only reacts to its own error.
        """
        self.assertFalse(self.client._is_structured_output_rejected(_thinking_level_rejected()))
        self.assertTrue(self.client._is_structured_output_rejected(_json_schema_rejected()))

    def test_overload_fallback_keeps_the_schema(self):
        """
        The 503 fallback model receives the same enforced schema.
        """
        self.generate.side_effect = [_model_overloaded(), _response("{}")]
        self.client.generate_content("p", response_schema=_SCHEMA)
        last = self.generate.call_args.kwargs
        self.assertEqual(last["model"], GoogleAIClient.FALLBACK_MODEL)
        self.assertEqual(last["config"].response_json_schema, _SCHEMA)


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

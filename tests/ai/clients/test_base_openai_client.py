import unittest
from unittest.mock import MagicMock, patch

import httpx2 as httpx
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    NotFoundError,
    RateLimitError,
)
from tenacity import RetryError

from app.ai.clients.base_client import AIClient
from app.ai.clients.base_openai_client import (
    REQUEST_TIMEOUT_S,
    OpenAIClient,
    OpenAIProviderConfig,
)

_REQUEST = httpx.Request("POST", "https://api.test-provider.com/v1")


def _response(status: int) -> httpx.Response:
    """
    Builds a bare HTTP response with the given status for SDK error construction.
    """
    return httpx.Response(status, request=_REQUEST)


def _stream(*contents):
    """
    Builds a fake streaming response: one chunk per content delta. A ``None``
    delta models a chunk that carries no text (e.g. role-only or final chunk).
    """
    return [MagicMock(choices=[MagicMock(delta=MagicMock(content=c))]) for c in contents]


def _reasoning_effort_rejected() -> BadRequestError:
    """
    Builds the 400 error a provider raises when a model doesn't support the
    ``reasoning_effort`` parameter (mirrors Groq's actual error message).
    """
    response = httpx.Response(
        400, request=httpx.Request("POST", "https://api.test-provider.com/v1")
    )
    return BadRequestError(
        "`reasoning_effort` is not supported with this model", response=response, body=None
    )


class ConcreteOpenAIClient(OpenAIClient):
    """
    Minimal concrete subclass used to test OpenAIClient behaviour without
    depending on any real provider credentials.
    """

    DEFAULT_MODEL = "test-model-v1"
    CONFIG = OpenAIProviderConfig(
        base_url="https://api.test-provider.com/v1",
        api_key_env="TEST_API_KEY",
    )


class TestOpenAIClientInit(unittest.TestCase):
    @patch("app.ai.clients.base_openai_client.OpenAI")
    def test_initializes_with_provided_api_key(self, mock_openai):
        """
        Passes the env var API key, base URL and request timeout to the OpenAI
        client on init.
        """
        with patch.dict("os.environ", {"TEST_API_KEY": "test-key-123"}):
            ConcreteOpenAIClient()

        mock_openai.assert_called_once_with(
            base_url="https://api.test-provider.com/v1",
            api_key="test-key-123",
            default_headers={},
            timeout=REQUEST_TIMEOUT_S,
        )

    @patch("app.ai.clients.base_openai_client.OpenAI")
    def test_logs_warning_when_api_key_not_set(self, mock_openai):
        """
        Emits a warning log when the required API key env var is not set.
        """
        with (
            patch.dict("os.environ", {}, clear=True),
            self.assertLogs("app.ai.clients.base_openai_client", level="WARNING") as cm,
        ):
            ConcreteOpenAIClient()

        self.assertIn("TEST_API_KEY", "\n".join(cm.output))


class TestOpenAIClientGetModelName(unittest.TestCase):
    @patch("app.ai.clients.base_openai_client.OpenAI")
    def test_returns_model_string(self, mock_openai):
        """
        Returns the model string passed at initialization.
        """
        with patch.dict("os.environ", {"TEST_API_KEY": "key"}):
            client = ConcreteOpenAIClient(model="gpt-4o")

        self.assertEqual(client.get_model_name(), "gpt-4o")


class TestOpenAIClientGenerateContent(unittest.TestCase):
    def setUp(self):
        """
        Patches time.sleep to avoid wait_exponential delay in tenacity retry,
        and clears the reasoning-unsupported cache so tests don't leak state.
        """
        # Patch time.sleep to avoid wait_exponential delay in tenacity retry
        self.sleep_patcher = patch("time.sleep")
        self.sleep_patcher.start()
        AIClient._reasoning_unsupported.clear()

    def tearDown(self):
        """
        Stops the sleep patcher started in setUp.
        """
        self.sleep_patcher.stop()

    @patch("app.ai.clients.base_openai_client.OpenAI")
    def test_returns_content_from_successful_api_call(self, mock_openai):
        """
        Accumulates the streamed deltas into the full response text.
        """
        mock_instance = mock_openai.return_value
        mock_instance.chat.completions.create.return_value = _stream("Generated ", "text")

        with patch.dict("os.environ", {"TEST_API_KEY": "key"}):
            client = ConcreteOpenAIClient()

        result = client.generate_content("Test prompt")

        self.assertEqual(result, "Generated text")

    @patch("app.ai.clients.base_openai_client.OpenAI")
    def test_raises_after_exhausting_retries_on_api_failure(self, mock_openai):
        """
        Propagates the exception after all tenacity retry attempts are exhausted.
        """
        mock_instance = mock_openai.return_value
        mock_instance.chat.completions.create.side_effect = APIConnectionError(request=_REQUEST)

        with patch.dict("os.environ", {"TEST_API_KEY": "key"}):
            client = ConcreteOpenAIClient()

        with self.assertRaises(RetryError):
            client.generate_content("Test prompt")
        self.assertEqual(mock_instance.chat.completions.create.call_count, 3)

    @patch("app.ai.clients.base_openai_client.OpenAI")
    def test_retries_transient_errors(self, mock_openai):
        """
        Timeouts, rate limits and 5xx responses are retried until attempts run out.
        """
        transient = [
            APITimeoutError(request=_REQUEST),
            RateLimitError("slow down", response=_response(429), body=None),
            InternalServerError("boom", response=_response(500), body=None),
            APIStatusError("bad gateway", response=_response(502), body=None),
        ]
        for exc in transient:
            with self.subTest(exc=type(exc).__name__):
                mock_instance = mock_openai.return_value
                mock_instance.chat.completions.create.reset_mock()
                mock_instance.chat.completions.create.side_effect = exc
                with patch.dict("os.environ", {"TEST_API_KEY": "key"}):
                    client = ConcreteOpenAIClient()
                with self.assertRaises(RetryError):
                    client.generate_content("Test prompt")
                self.assertEqual(mock_instance.chat.completions.create.call_count, 3)

    @patch("app.ai.clients.base_openai_client.OpenAI")
    def test_does_not_retry_permanent_errors(self, mock_openai):
        """
        Auth failures, bad requests, missing models and unknown errors fail on the first attempt.
        """
        permanent = [
            AuthenticationError("bad key", response=_response(401), body=None),
            BadRequestError("bad request", response=_response(400), body=None),
            NotFoundError("no model", response=_response(404), body=None),
            RuntimeError("unexpected"),
        ]
        for exc in permanent:
            with self.subTest(exc=type(exc).__name__):
                mock_instance = mock_openai.return_value
                mock_instance.chat.completions.create.reset_mock()
                mock_instance.chat.completions.create.side_effect = exc
                with patch.dict("os.environ", {"TEST_API_KEY": "key"}):
                    client = ConcreteOpenAIClient()
                with self.assertRaises(type(exc)):
                    client.generate_content("Test prompt")
                self.assertEqual(mock_instance.chat.completions.create.call_count, 1)

    @patch("app.ai.clients.base_openai_client.OpenAI")
    def test_calls_api_with_correct_model_and_messages(self, mock_openai):
        """
        Sends the prompt in the expected message format with the configured
        model, requesting a streamed response.
        """
        mock_instance = mock_openai.return_value
        mock_instance.chat.completions.create.return_value = _stream("OK")

        with patch.dict("os.environ", {"TEST_API_KEY": "key"}):
            client = ConcreteOpenAIClient(model="test-model-v1")

        client.generate_content("Hello!")

        mock_instance.chat.completions.create.assert_called_once_with(
            model="test-model-v1",
            messages=[{"role": "user", "content": "Hello!"}],
            extra_body={"reasoning_effort": "low"},
            stream=True,
        )

    @patch("app.ai.clients.base_openai_client.OpenAI")
    def test_retries_without_reasoning_effort_when_model_rejects_it(self, mock_openai):
        """
        Transparently retries the same call with reasoning_effort dropped when
        the model rejects it, so non-reasoning models need no special-casing.
        """
        mock_instance = mock_openai.return_value
        mock_instance.chat.completions.create.side_effect = [
            _reasoning_effort_rejected(),
            _stream("OK"),
        ]

        with patch.dict("os.environ", {"TEST_API_KEY": "key"}):
            client = ConcreteOpenAIClient()

        result = client.generate_content("Hello!")

        self.assertEqual(result, "OK")
        self.assertEqual(mock_instance.chat.completions.create.call_count, 2)
        mock_instance.chat.completions.create.assert_called_with(
            model="test-model-v1",
            messages=[{"role": "user", "content": "Hello!"}],
            extra_body={},
            stream=True,
        )

    @patch("app.ai.clients.base_openai_client.OpenAI")
    def test_skips_reasoning_effort_on_subsequent_calls_after_rejection(self, mock_openai):
        """
        Remembers a model's rejection of reasoning_effort across calls, so
        later requests to the same model don't pay for the failing round trip.
        """
        mock_instance = mock_openai.return_value
        mock_instance.chat.completions.create.side_effect = [
            _reasoning_effort_rejected(),
            _stream("OK"),
            _stream("OK again"),
        ]

        with patch.dict("os.environ", {"TEST_API_KEY": "key"}):
            client = ConcreteOpenAIClient()

        client.generate_content("Hello!")
        client.generate_content("Hello again!")

        self.assertEqual(mock_instance.chat.completions.create.call_count, 3)
        mock_instance.chat.completions.create.assert_called_with(
            model="test-model-v1",
            messages=[{"role": "user", "content": "Hello again!"}],
            extra_body={},
            stream=True,
        )

    @patch("app.ai.clients.base_openai_client.OpenAI")
    def test_returns_empty_string_when_no_content_streamed(self, mock_openai):
        """
        Returns an empty string when the stream yields no text deltas.
        """
        mock_instance = mock_openai.return_value
        mock_instance.chat.completions.create.return_value = _stream(None)

        with patch.dict("os.environ", {"TEST_API_KEY": "key"}):
            client = ConcreteOpenAIClient()

        result = client.generate_content("Test prompt")

        self.assertEqual(result, "")

    @patch("app.ai.clients.base_openai_client.OpenAI")
    def test_logs_time_to_first_token(self, mock_openai):
        """
        Emits a first-token log as soon as the first delta arrives, so a slow
        generation is observably progressing rather than appearing hung.
        """
        mock_instance = mock_openai.return_value
        mock_instance.chat.completions.create.return_value = _stream("hello")

        with patch.dict("os.environ", {"TEST_API_KEY": "key"}):
            client = ConcreteOpenAIClient()

        with self.assertLogs("app.ai.clients.base_openai_client", level="INFO") as cm:
            client.generate_content("Test prompt")

        self.assertTrue(any("first token" in line for line in cm.output))

    @patch("app.ai.clients.base_openai_client.OpenAI")
    def test_maps_reasoning_to_reasoning_effort(self, mock_openai):
        """
        An explicit level becomes reasoning_effort; ``reasoning`` never reaches the SDK.
        """
        mock_instance = mock_openai.return_value
        mock_instance.chat.completions.create.return_value = _stream("OK")
        with patch.dict("os.environ", {"TEST_API_KEY": "key"}):
            client = ConcreteOpenAIClient()

        client.generate_content("Hello!", reasoning="medium")

        kwargs = mock_instance.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs["extra_body"], {"reasoning_effort": "medium"})
        self.assertNotIn("reasoning", kwargs)

    @patch("app.ai.clients.base_openai_client.OpenAI")
    def test_default_reasoning_effort_is_low_and_not_forwarded(self, mock_openai):
        """
        Without a level the shared default is sent, and no ``reasoning`` kwarg leaks.
        """
        mock_instance = mock_openai.return_value
        mock_instance.chat.completions.create.return_value = _stream("OK")
        with patch.dict("os.environ", {"TEST_API_KEY": "key"}):
            client = ConcreteOpenAIClient()

        client.generate_content("Hello!")

        kwargs = mock_instance.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs["extra_body"], {"reasoning_effort": "low"})
        self.assertNotIn("reasoning", kwargs)

    @patch("app.ai.clients.base_openai_client.OpenAI")
    def test_reasoning_fallback_works_with_non_default_level(self, mock_openai):
        """
        A model rejecting a HIGH reasoning_effort is retried without it.
        """
        mock_instance = mock_openai.return_value
        mock_instance.chat.completions.create.side_effect = [
            _reasoning_effort_rejected(),
            _stream("OK"),
        ]
        with patch.dict("os.environ", {"TEST_API_KEY": "key"}):
            client = ConcreteOpenAIClient()

        self.assertEqual(client.generate_content("Hello!", reasoning="high"), "OK")

        calls = mock_instance.chat.completions.create.call_args_list
        self.assertEqual(calls[0].kwargs["extra_body"], {"reasoning_effort": "high"})
        self.assertEqual(calls[1].kwargs["extra_body"], {})
        for call in calls:
            self.assertNotIn("reasoning", call.kwargs)


_SCHEMA = {
    "type": "object",
    "properties": {"a": {"type": "integer"}},
    "required": ["a"],
    "additionalProperties": False,
}


def _structured_output_rejected(status: int = 400, mode: str = "json_schema") -> APIStatusError:
    """
    Builds the error a provider raises when a model doesn't support a
    ``response_format`` mode (mirrors Groq's actual error message).
    """
    response = _response(status)
    message = f"`response_format` of type `{mode}` is not supported with this model"
    error_cls = {400: BadRequestError, 404: NotFoundError}.get(status, APIStatusError)
    return error_cls(message, response=response, body=None)


class TestOpenAIClientStructuredOutput(unittest.TestCase):
    """
    ``response_schema`` maps to ``response_format``, degrading on rejection.
    """

    def setUp(self):
        """
        Patches the OpenAI SDK and sleep, and clears the shared rejection memories.
        """
        sleep_patcher = patch("time.sleep")
        sleep_patcher.start()
        self.addCleanup(sleep_patcher.stop)
        openai_patcher = patch("app.ai.clients.base_openai_client.OpenAI")
        self.create = openai_patcher.start().return_value.chat.completions.create
        self.addCleanup(openai_patcher.stop)
        AIClient._reasoning_unsupported.clear()
        AIClient._structured_rejected.clear()
        self.addCleanup(AIClient._structured_rejected.clear)
        with patch.dict("os.environ", {"TEST_API_KEY": "key"}):
            self.client = ConcreteOpenAIClient()

    def formats(self) -> list:
        """
        The response_format of every request sent, in order (None when absent).
        """
        return [c.kwargs.get("response_format") for c in self.create.call_args_list]

    def test_schema_mode_sends_strict_json_schema(self):
        """
        The strongest mode asks the provider to enforce the schema strictly.
        """
        self.create.return_value = _stream('{"a": 1}')
        self.assertEqual(self.client.generate_content("p", response_schema=_SCHEMA), '{"a": 1}')
        self.assertEqual(
            self.formats(),
            [
                {
                    "type": "json_schema",
                    "json_schema": {"name": "response", "schema": _SCHEMA, "strict": True},
                }
            ],
        )
        self.assertEqual(self.client.last_structured_mode, "schema")

    def test_no_schema_sends_no_response_format(self):
        """
        Plain-text requests are unchanged.
        """
        self.create.return_value = _stream("ok")
        self.client.generate_content("p")
        self.assertEqual(self.formats(), [None])

    def test_degrades_to_json_object_then_prompt_only(self):
        """
        A rejected json_schema falls to json_object, then to no response_format.
        """
        self.create.side_effect = [
            _structured_output_rejected(mode="json_schema"),
            _structured_output_rejected(mode="json_object"),
            _stream('{"a": 1}'),
        ]
        self.client.generate_content("p", response_schema=_SCHEMA)
        self.assertEqual(self.formats()[1:], [{"type": "json_object"}, None])
        last_prompt = self.create.call_args.kwargs["messages"][0]["content"]
        self.assertIn('"additionalProperties": false', last_prompt)
        self.assertEqual(self.client.last_structured_mode, "prompt")

    def test_rejection_is_remembered_for_the_model(self):
        """
        Later calls skip the modes the model already rejected.
        """
        self.create.side_effect = [
            _structured_output_rejected(),
            _stream("{}"),
            _stream("{}"),
        ]
        self.client.generate_content("p", response_schema=_SCHEMA)
        self.client.generate_content("p", response_schema=_SCHEMA)
        self.assertEqual(self.formats()[2], {"type": "json_object"})

    def test_schema_validation_failure_is_an_invalid_response(self):
        """
        Output failing the provider's schema check surfaces as a retryable invalid
        response, sent once and without degrading the remembered mode.
        """
        from app.ai.clients.base_client import InvalidAIResponseError

        message = "Failed to validate JSON. code: json_validate_failed"
        self.create.side_effect = BadRequestError(message, response=_response(400), body=None)

        with self.assertRaises(InvalidAIResponseError):
            self.client.generate_content("p", response_schema=_SCHEMA)

        self.assertEqual(self.create.call_count, 1)
        self.assertEqual(AIClient._structured_rejected, set())

    def test_recognises_unprocessable_and_not_found_rejections(self):
        """
        Routers answer an unsupported parameter with 404 or 422 as well as 400.
        """
        for status in (404, 422):
            with self.subTest(status=status):
                self.assertTrue(
                    self.client._is_structured_output_rejected(
                        _structured_output_rejected(status=status)
                    )
                )

    def test_recognises_a_router_wrapped_upstream_rejection(self):
        """
        Routers forward the upstream refusal inside a generic "Provider returned error".
        """
        exc = BadRequestError(
            "Provider returned error: model features structured outputs not support",
            response=_response(400),
            body=None,
        )
        self.assertTrue(self.client._is_structured_output_rejected(exc))
        hyphenated = BadRequestError(
            "Provider returned error: model does not support feature: structured-outputs",
            response=_response(400),
            body=None,
        )
        self.assertTrue(self.client._is_structured_output_rejected(hyphenated))

    def test_reasoning_rejection_is_not_a_structured_rejection(self):
        """
        The two fallbacks are independent: each only reacts to its own error.
        """
        self.assertFalse(self.client._is_structured_output_rejected(_reasoning_effort_rejected()))

    def test_reasoning_and_schema_fallbacks_compose(self):
        """
        A model rejecting reasoning_effort keeps its enforced schema.
        """
        self.create.side_effect = [_reasoning_effort_rejected(), _stream("{}")]
        self.client.generate_content("p", response_schema=_SCHEMA)
        last = self.create.call_args.kwargs
        self.assertEqual(last["response_format"]["type"], "json_schema")
        self.assertEqual(last["extra_body"], {})

    def test_unrelated_bad_request_propagates(self):
        """
        A 400 that isn't about response_format is not treated as a mode rejection.
        """
        self.create.side_effect = BadRequestError(
            "context length exceeded", response=_response(400), body=None
        )
        with self.assertRaises(BadRequestError):
            self.client.generate_content("p", response_schema=_SCHEMA)
        self.assertEqual(AIClient._structured_rejected, set())


if __name__ == "__main__":
    unittest.main()

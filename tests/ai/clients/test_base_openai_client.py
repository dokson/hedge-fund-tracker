import unittest
from unittest.mock import MagicMock, patch

from tenacity import RetryError

from app.ai.clients.base_openai_client import (
    REQUEST_TIMEOUT_S,
    OpenAIClient,
    OpenAIProviderConfig,
)


def _stream(*contents):
    """
    Builds a fake streaming response: one chunk per content delta. A ``None``
    delta models a chunk that carries no text (e.g. role-only or final chunk).
    """
    return [MagicMock(choices=[MagicMock(delta=MagicMock(content=c))]) for c in contents]


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
        Patches time.sleep to avoid wait_exponential delay in tenacity retry.
        """
        # Patch time.sleep to avoid wait_exponential delay in tenacity retry
        self.sleep_patcher = patch("time.sleep")
        self.sleep_patcher.start()

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
        mock_instance.chat.completions.create.side_effect = RuntimeError("API unavailable")

        with patch.dict("os.environ", {"TEST_API_KEY": "key"}):
            client = ConcreteOpenAIClient()

        with self.assertRaises(RetryError):
            client.generate_content("Test prompt")

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


if __name__ == "__main__":
    unittest.main()

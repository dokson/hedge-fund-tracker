import unittest
from unittest.mock import patch, MagicMock
from app.ai.clients.base_openai_client import OpenAIClient


class ConcreteOpenAIClient(OpenAIClient):
    """
    Minimal concrete subclass used to test OpenAIClient abstract behavior
    without depending on any real provider credentials.
    """
    DEFAULT_MODEL = 'test-model-v1'

    def __init__(self, model=DEFAULT_MODEL):
        """
        Delegates initialization to OpenAIClient with test provider settings.
        """
        super().__init__(model)

    def get_base_url(self) -> str:
        """
        Returns the test provider base URL.
        """
        return 'https://api.test-provider.com/v1'

    def get_api_key_env_var(self) -> str:
        """
        Returns the test env var name for the API key.
        """
        return 'TEST_API_KEY'


class TestOpenAIClientInit(unittest.TestCase):

    @patch('app.ai.clients.base_openai_client.OpenAI')
    def test_initializes_with_provided_api_key(self, mock_openai):
        """
        Passes the env var API key and base URL to the OpenAI client on init.
        """
        with patch.dict('os.environ', {'TEST_API_KEY': 'test-key-123'}):
            client = ConcreteOpenAIClient()

        mock_openai.assert_called_once_with(
            base_url='https://api.test-provider.com/v1',
            api_key='test-key-123',
            default_headers={}
        )

    @patch('app.ai.clients.base_openai_client.OpenAI')
    def test_prints_warning_when_api_key_not_set(self, mock_openai):
        """
        Prints a warning when the required API key env var is not set.
        """
        with patch.dict('os.environ', {}, clear=True):
            with patch('builtins.print') as mock_print:
                ConcreteOpenAIClient()

        printed_messages = ' '.join(str(call) for call in mock_print.call_args_list)
        self.assertIn('TEST_API_KEY', printed_messages)

    @patch('app.ai.clients.base_openai_client.OpenAI')
    def test_stores_model_name(self, mock_openai):
        """
        Stores the model string as an instance attribute.
        """
        with patch.dict('os.environ', {'TEST_API_KEY': 'key'}):
            client = ConcreteOpenAIClient(model='custom-model')

        self.assertEqual(client.model, 'custom-model')


class TestOpenAIClientGetModelName(unittest.TestCase):

    @patch('app.ai.clients.base_openai_client.OpenAI')
    def test_returns_model_string(self, mock_openai):
        """
        Returns the model string passed at initialization.
        """
        with patch.dict('os.environ', {'TEST_API_KEY': 'key'}):
            client = ConcreteOpenAIClient(model='gpt-4o')

        self.assertEqual(client.get_model_name(), 'gpt-4o')


class TestOpenAIClientDefaults(unittest.TestCase):

    @patch('app.ai.clients.base_openai_client.OpenAI')
    def test_get_headers_returns_empty_dict_by_default(self, mock_openai):
        """
        get_headers() returns an empty dict unless overridden by subclass.
        """
        with patch.dict('os.environ', {'TEST_API_KEY': 'key'}):
            client = ConcreteOpenAIClient()

        self.assertEqual(client.get_headers(), {})

    @patch('app.ai.clients.base_openai_client.OpenAI')
    def test_get_extra_body_returns_empty_dict_by_default(self, mock_openai):
        """
        get_extra_body() returns an empty dict unless overridden by subclass.
        """
        with patch.dict('os.environ', {'TEST_API_KEY': 'key'}):
            client = ConcreteOpenAIClient()

        self.assertEqual(client.get_extra_body(), {})


class TestOpenAIClientGenerateContent(unittest.TestCase):

    def setUp(self):
        """
        Patches time.sleep to avoid wait_exponential delay in tenacity retry.
        """
        # Patch time.sleep to avoid wait_exponential delay in tenacity retry
        self.sleep_patcher = patch('time.sleep')
        self.sleep_patcher.start()

    def tearDown(self):
        """
        Stops the sleep patcher started in setUp.
        """
        self.sleep_patcher.stop()

    @patch('app.ai.clients.base_openai_client.OpenAI')
    def test_returns_content_from_successful_api_call(self, mock_openai):
        """
        Returns the text content from the first choice in the API response.
        """
        mock_instance = mock_openai.return_value
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='Generated text'))]
        mock_instance.chat.completions.create.return_value = mock_response

        with patch.dict('os.environ', {'TEST_API_KEY': 'key'}):
            client = ConcreteOpenAIClient()

        result = client.generate_content('Test prompt')

        self.assertEqual(result, 'Generated text')

    @patch('app.ai.clients.base_openai_client.OpenAI')
    def test_raises_after_exhausting_retries_on_api_failure(self, mock_openai):
        """
        Propagates the exception after all tenacity retry attempts are exhausted.
        """
        mock_instance = mock_openai.return_value
        mock_instance.chat.completions.create.side_effect = Exception('API unavailable')

        with patch.dict('os.environ', {'TEST_API_KEY': 'key'}):
            client = ConcreteOpenAIClient()

        with self.assertRaises(Exception):
            client.generate_content('Test prompt')

    @patch('app.ai.clients.base_openai_client.OpenAI')
    def test_calls_api_with_correct_model_and_messages(self, mock_openai):
        """
        Sends the prompt in the expected message format with the configured model.
        """
        mock_instance = mock_openai.return_value
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='OK'))]
        mock_instance.chat.completions.create.return_value = mock_response

        with patch.dict('os.environ', {'TEST_API_KEY': 'key'}):
            client = ConcreteOpenAIClient(model='test-model-v1')

        client.generate_content('Hello!')

        mock_instance.chat.completions.create.assert_called_once_with(
            model='test-model-v1',
            messages=[{'role': 'user', 'content': 'Hello!'}],
            extra_body={}
        )

    @patch('app.ai.clients.base_openai_client.OpenAI')
    def test_returns_empty_string_when_content_is_none(self, mock_openai):
        """
        Returns an empty string when the API response content is None.
        """
        mock_instance = mock_openai.return_value
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=None))]
        mock_instance.chat.completions.create.return_value = mock_response

        with patch.dict('os.environ', {'TEST_API_KEY': 'key'}):
            client = ConcreteOpenAIClient()

        result = client.generate_content('Test prompt')

        self.assertEqual(result, '')


if __name__ == '__main__':
    unittest.main()

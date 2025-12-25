import unittest
from unittest.mock import patch, MagicMock
from app.ai.clients.openrouter_client import OpenRouterClient

class TestOpenRouterClient(unittest.TestCase):
    def setUp(self):
        self.openrouter_api_key = "test_openrouter_api_key"
        with patch.dict('os.environ', {'OPENROUTER_API_KEY': self.openrouter_api_key}):
            self.client = OpenRouterClient()

    @patch('app.ai.clients.base_openai_client.OpenAI')
    def test_generate_content_invocation(self, mock_openai):
        # Setup mock
        mock_instance = mock_openai.return_value
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Mocked OpenRouter response"))]
        mock_instance.chat.completions.create.return_value = mock_response

        # Re-initialize client to pick up mocked OpenAI instance
        with patch.dict('os.environ', {'OPENROUTER_API_KEY': self.openrouter_api_key}):
            client = OpenRouterClient()
        
        prompt = "Hello, OpenRouter!"
        response = client.generate_content(prompt)

        # Assertions
        self.assertEqual(response, "Mocked OpenRouter response")
        mock_instance.chat.completions.create.assert_called_once_with(
            model=OpenRouterClient.DEFAULT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            extra_body={}
        )
        
        # Verify base_url and headers
        mock_openai.assert_called_with(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.openrouter_api_key,
            default_headers={
                "HTTP-Referer": "https://github.com/dokson/hedge-fund-tracker",
                "X-Title": "Hedge Fund Tracker"
            }
        )

if __name__ == '__main__':
    unittest.main()

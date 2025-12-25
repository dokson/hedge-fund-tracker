import unittest
from unittest.mock import patch, MagicMock
from app.ai.clients.groq_client import GroqClient

class TestGroqClient(unittest.TestCase):
    def setUp(self):
        self.groq_api_key = "test_groq_api_key"
        with patch.dict('os.environ', {'GROQ_API_KEY': self.groq_api_key}):
            self.client = GroqClient()

    @patch('app.ai.clients.base_openai_client.OpenAI')
    def test_generate_content_invocation(self, mock_openai):
        # Setup mock
        mock_instance = mock_openai.return_value
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Mocked Groq response"))]
        mock_instance.chat.completions.create.return_value = mock_response

        # Re-initialize client to pick up mocked OpenAI instance
        with patch.dict('os.environ', {'GROQ_API_KEY': self.groq_api_key}):
            client = GroqClient()
        
        prompt = "Hello, Groq!"
        response = client.generate_content(prompt)

        # Assertions
        self.assertEqual(response, "Mocked Groq response")
        mock_instance.chat.completions.create.assert_called_once_with(
            model=GroqClient.DEFAULT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            extra_body={}
        )
        
        # Verify base_url
        mock_openai.assert_called_with(
            base_url="https://api.groq.com/openai/v1",
            api_key=self.groq_api_key,
            default_headers={}
        )

if __name__ == '__main__':
    unittest.main()

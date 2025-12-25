import unittest
from unittest.mock import patch, MagicMock
from app.ai.clients.google_client import GoogleAIClient

class TestGoogleAIClient(unittest.TestCase):
    def setUp(self):
        # We don't need a real API key for mocking, genai.Client() will just use env vars
        self.client = GoogleAIClient()

    @patch('app.ai.clients.google_client.genai.Client')
    def test_generate_content_invocation(self, mock_genai_client):
        # Setup mock
        mock_instance = mock_genai_client.return_value
        mock_response = MagicMock()
        mock_response.text = "Mocked Gemini response"
        mock_instance.models.generate_content.return_value = mock_response

        # Re-initialize client to pick up mocked genai Client instance
        client = GoogleAIClient()
        
        prompt = "Hello, Gemini!"
        response = client.generate_content(prompt)

        # Assertions
        self.assertEqual(response, "Mocked Gemini response")
        mock_instance.models.generate_content.assert_called_once_with(
            model=GoogleAIClient.DEFAULT_MODEL,
            contents=prompt
        )
        
        # Verify provider name in get_model_name
        self.assertEqual(client.get_model_name(), f"google/{GoogleAIClient.DEFAULT_MODEL}")

if __name__ == '__main__':
    unittest.main()

import unittest
from unittest.mock import patch, MagicMock
from app.ai.clients.google_client import GoogleAIClient

class TestGoogleAIClient(unittest.TestCase):
    def setUp(self):
        # Patch genai.Client globally for the setup to avoid ValueError in CI
        self.patcher = patch('app.ai.clients.google_client.genai.Client')
        self.mock_genai_client = self.patcher.start()
        
        # Setup mock instance
        self.mock_instance = self.mock_genai_client.return_value
        self.mock_response = MagicMock()
        self.mock_response.text = "Mocked Gemini response"
        self.mock_instance.models.generate_content.return_value = self.mock_response
        
        self.client = GoogleAIClient()

    def tearDown(self):
        self.patcher.stop()

    def test_generate_content_invocation(self):
        prompt = "Hello, Gemini!"
        response = self.client.generate_content(prompt)

        # Assertions
        self.assertEqual(response, "Mocked Gemini response")
        self.mock_instance.models.generate_content.assert_called_once_with(
            model=GoogleAIClient.DEFAULT_MODEL,
            contents=prompt
        )
        
        # Verify provider name in get_model_name
        self.assertEqual(self.client.get_model_name(), f"google/{GoogleAIClient.DEFAULT_MODEL}")

if __name__ == '__main__':
    unittest.main()

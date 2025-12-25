import unittest
from unittest.mock import patch, MagicMock
from app.ai.clients.github_client import GitHubClient

class TestGitHubClient(unittest.TestCase):
    def setUp(self):
        self.github_token = "test_github_token"
        with patch.dict('os.environ', {'GITHUB_TOKEN': self.github_token}):
            self.client = GitHubClient()

    @patch('app.ai.clients.base_openai_client.OpenAI')
    def test_generate_content_invocation(self, mock_openai):
        # Setup mock
        mock_instance = mock_openai.return_value
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Mocked response"))]
        mock_instance.chat.completions.create.return_value = mock_response

        # Re-initialize client to pick up mocked OpenAI instance
        with patch.dict('os.environ', {'GITHUB_TOKEN': self.github_token}):
            client = GitHubClient()
        
        prompt = "Hello, GitHub Models!"
        response = client.generate_content(prompt)

        # Assertions
        self.assertEqual(response, "Mocked response")
        mock_instance.chat.completions.create.assert_called_once_with(
            model=GitHubClient.DEFAULT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            extra_body={}
        )
        
        # Verify base_url
        mock_openai.assert_called_with(
            base_url="https://models.github.ai/inference",
            api_key=self.github_token,
            default_headers={}
        )

if __name__ == '__main__':
    unittest.main()

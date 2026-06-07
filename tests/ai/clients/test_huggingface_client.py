import unittest
from unittest.mock import ANY, MagicMock, patch

from app.ai.clients.huggingface_client import HuggingFaceClient


class TestHuggingFaceClient(unittest.TestCase):
    def setUp(self):
        self.hf_token = "test_hf_token"
        with patch.dict("os.environ", {"HF_TOKEN": self.hf_token}):
            self.client = HuggingFaceClient()

    @patch("app.ai.clients.base_openai_client.OpenAI")
    def test_generate_content_invocation(self, mock_openai):
        # Setup mock
        mock_instance = mock_openai.return_value
        mock_instance.chat.completions.create.return_value = [
            MagicMock(choices=[MagicMock(delta=MagicMock(content="Mocked HF response"))])
        ]

        # Re-initialize client to pick up mocked OpenAI instance
        with patch.dict("os.environ", {"HF_TOKEN": self.hf_token}):
            client = HuggingFaceClient()

        prompt = "Hello, Hugging Face!"
        response = client.generate_content(prompt)

        # Assertions
        self.assertEqual(response, "Mocked HF response")
        mock_instance.chat.completions.create.assert_called_once_with(
            model=HuggingFaceClient.DEFAULT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            extra_body={},
            stream=True,
        )

        # Verify base_url
        mock_openai.assert_called_with(
            base_url="https://router.huggingface.co/v1/",
            api_key=self.hf_token,
            default_headers={},
            timeout=ANY,
        )


if __name__ == "__main__":
    unittest.main()

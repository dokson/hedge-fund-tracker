import unittest
import os
import shutil
import glob
from app.ai.clients.base_client import AIClient


class MockAIClient(AIClient):
    """
    Mock client for testing
    """
    def _generate_content_impl(self, prompt: str, **kwargs) -> str:
        return f"Response to: {prompt}"

    def get_model_name(self) -> str:
        return "mock-model"


class TestBaseClient(unittest.TestCase):
    def setUp(self):
        self.cache_dir = AIClient.CACHE_DIR
        self.client = MockAIClient()
        # Clean cache before tests
        if os.path.exists(self.cache_dir):
            shutil.rmtree(self.cache_dir)


    def tearDown(self):
        # Clean up after tests
        if os.path.exists(self.cache_dir):
            shutil.rmtree(self.cache_dir)


    def test_log_response_creates_file(self):
        """
        Test that generate_content creates a log file
        """
        self.client.generate_content("Test Prompt")
        
        files = glob.glob(os.path.join(self.cache_dir, "response_*.log"))
        self.assertEqual(len(files), 1)
        
        with open(files[0], 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn("Model: mock-model", content)
            self.assertIn("Prompt:\nTest Prompt", content)
            self.assertIn("Response:\nResponse to: Test Prompt", content)


    def test_log_limit_retention(self):
        """
        Test that the logger keeps only the last LOG_RETENTION_LIMIT files
        """
        limit = AIClient.LOG_RETENTION_LIMIT
        # Create a few more files than the limit
        for i in range(limit + 5):
            self.client.generate_content(f"Prompt {i}")

        files = glob.glob(os.path.join(self.cache_dir, "response_*.log"))
        self.assertEqual(len(files), limit)


if __name__ == '__main__':
    unittest.main()

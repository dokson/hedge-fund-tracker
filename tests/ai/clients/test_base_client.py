import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
        """
        Use an isolated tempdir as cache root so tests can't wipe or pollute
        the real ``__llmcache__/`` directory in the repo.
        """
        self.cache_dir = tempfile.mkdtemp(prefix="hft_llmcache_")
        cache_patcher = patch.object(AIClient, "CACHE_DIR", self.cache_dir)
        self.addCleanup(cache_patcher.stop)
        cache_patcher.start()
        self.client = MockAIClient()

    def tearDown(self):
        """
        Remove the tempdir; ignore errors on Windows file-locking edge cases.
        """
        shutil.rmtree(self.cache_dir, ignore_errors=True)

    def test_log_response_creates_file(self):
        """
        Test that generate_content creates a log file
        """
        self.client.generate_content("Test Prompt")

        files = list(Path(self.cache_dir).glob("response_*.log"))
        self.assertEqual(len(files), 1)

        with files[0].open(encoding="utf-8") as f:
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

        files = list(Path(self.cache_dir).glob("response_*.log"))
        self.assertEqual(len(files), limit)


if __name__ == "__main__":
    unittest.main()

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.ai.clients.base_client import DEFAULT_REASONING, AIClient


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

    def test_log_failure_message_has_no_duplicate_marker(self):
        """
        The error level already prefixes its own marker, so the body must not repeat "Warning:".
        """
        with (
            patch("pathlib.Path.open", side_effect=OSError("disk full")),
            self.assertLogs("app.ai.clients.base_client", level="ERROR") as cm,
        ):
            self.client._log_response("p", "r")

        self.assertEqual([r.getMessage() for r in cm.records], ["Failed to log AI response"])


class _ReasoningRejectedError(Exception):
    """
    Fake provider error signalling that the reasoning parameter was rejected.
    """


class ReasoningFakeClient(AIClient):
    """
    Minimal provider: records the reasoning level of every request and rejects
    it for the models listed in ``rejecting``.
    """

    def __init__(self, model: str = "fake-model", rejecting: frozenset[str] = frozenset()):
        """
        Stores the model and the models that reject a reasoning level.
        """
        self.model = model
        self.rejecting = rejecting
        self.sent: list[tuple[str, str | None]] = []

    def _generate_content_impl(self, prompt: str, reasoning=None, **kwargs) -> str:
        """
        Routes the request through the shared reasoning flow.
        """
        return self._generate_with_reasoning(
            self.model, reasoning, lambda level: self._send(self.model, level)
        )

    def _send(self, model: str, level: str | None) -> str:
        """
        Records one request and fails when the model rejects the level.
        """
        self.sent.append((model, level))
        if level is not None and model in self.rejecting:
            raise _ReasoningRejectedError("reasoning not supported")
        return "ok"

    def _is_reasoning_rejected(self, exc: BaseException) -> bool:
        """
        Recognises the fake rejection error.
        """
        return isinstance(exc, _ReasoningRejectedError)

    def get_model_name(self) -> str:
        """
        Returns the fake model name.
        """
        return self.model


class TestSharedReasoningFlow(unittest.TestCase):
    """
    The reasoning level, its validation and the rejection memory live in AIClient.
    """

    def setUp(self):
        """
        Isolates the response cache and the shared rejection memory.
        """
        self.cache_dir = tempfile.mkdtemp(prefix="hft_llmcache_")
        cache_patcher = patch.object(AIClient, "CACHE_DIR", self.cache_dir)
        self.addCleanup(cache_patcher.stop)
        cache_patcher.start()
        self.addCleanup(shutil.rmtree, self.cache_dir, True)
        AIClient._reasoning_unsupported.clear()
        self.addCleanup(AIClient._reasoning_unsupported.clear)

    def test_default_level_is_low(self):
        """
        Omitting the level sends the shared default.
        """
        client = ReasoningFakeClient()
        client.generate_content("p")
        self.assertEqual(DEFAULT_REASONING, "low")
        self.assertEqual(client.sent, [("fake-model", "low")])

    def test_explicit_level_is_forwarded(self):
        """
        An explicit level reaches the provider unchanged.
        """
        client = ReasoningFakeClient()
        client.generate_content("p", reasoning="medium")
        self.assertEqual(client.sent, [("fake-model", "medium")])

    def test_rejection_retries_without_level_and_is_remembered(self):
        """
        A rejecting model is retried without a level, then skipped straight to it.
        """
        client = ReasoningFakeClient(rejecting=frozenset({"fake-model"}))
        self.assertEqual(client.generate_content("p", reasoning="high"), "ok")
        client.generate_content("p")
        self.assertEqual(
            client.sent,
            [("fake-model", "high"), ("fake-model", None), ("fake-model", None)],
        )

    def test_memory_is_per_model(self):
        """
        One model's rejection doesn't strip the level from another model.
        """
        ReasoningFakeClient(model="old", rejecting=frozenset({"old"})).generate_content("p")
        other = ReasoningFakeClient(model="new")
        other.generate_content("p")
        self.assertEqual(other.sent, [("new", "low")])

    def test_memory_is_per_provider(self):
        """
        The same model name on a different provider is tracked separately.
        """

        class OtherProvider(ReasoningFakeClient):
            """
            A second provider serving a model with the same name.
            """

        ReasoningFakeClient(rejecting=frozenset({"fake-model"})).generate_content("p")
        other = OtherProvider()
        other.generate_content("p")
        self.assertEqual(other.sent, [("fake-model", "low")])

    def test_unrelated_errors_propagate(self):
        """
        Only a recognised rejection triggers the retry.
        """
        client = ReasoningFakeClient()
        with (
            patch.object(client, "_send", side_effect=RuntimeError("boom")),
            self.assertRaises(RuntimeError),
        ):
            client.generate_content("p")
        self.assertEqual(AIClient._reasoning_unsupported, set())

    def test_invalid_level_is_rejected(self):
        """
        An unknown level fails fast, before any provider call.
        """
        client = ReasoningFakeClient()
        with self.assertRaises(ValueError):
            client.generate_content("p", reasoning="extreme")  # type: ignore[arg-type]
        self.assertEqual(client.sent, [])


if __name__ == "__main__":
    unittest.main()

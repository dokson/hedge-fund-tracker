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


class _StructureRejectedError(Exception):
    """
    Fake provider error signalling that a structured-output mode was rejected.
    """


_SCHEMA = {
    "type": "object",
    "properties": {"a": {"type": "integer"}},
    "required": ["a"],
    "additionalProperties": False,
}


class StructuredFakeClient(AIClient):
    """
    Minimal provider supporting every structured mode; ``rejecting`` maps a
    model to the modes it refuses.
    """

    SUPPORTED_STRUCTURED_MODES = ("schema", "json", "prompt")

    def __init__(self, model: str = "fake-model", rejecting: dict | None = None):
        """
        Stores the model and the modes each model rejects.
        """
        self.model = model
        self.rejecting = rejecting or {}
        self.sent: list[tuple[str | None, str]] = []

    def _generate_content_impl(self, prompt: str, reasoning=None, response_schema=None, **kwargs):
        """
        Routes the request through the shared structured-output flow.
        """
        return self._generate_with_structure(self.model, prompt, response_schema, self._send)

    def _send(self, prompt: str, mode) -> str:
        """
        Records one request and fails when the model rejects its mode.
        """
        self.sent.append((mode, prompt))
        if mode in self.rejecting.get(self.model, ()):
            raise _StructureRejectedError(f"{mode} not supported")
        return '{"a": 1}'

    def _is_structured_output_rejected(self, exc: BaseException) -> bool:
        """
        Recognises the fake rejection error.
        """
        return isinstance(exc, _StructureRejectedError)

    def get_model_name(self) -> str:
        """
        Returns the fake model name.
        """
        return self.model


class TestSharedStructuredOutputFlow(unittest.TestCase):
    """
    Structured-output mode selection, degradation and memory live in AIClient.
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
        AIClient._structured_rejected.clear()
        self.addCleanup(AIClient._structured_rejected.clear)

    def modes(self, client: StructuredFakeClient) -> list:
        """
        The mode of every recorded request, in order.
        """
        return [mode for mode, _ in client.sent]

    def test_schema_mode_is_tried_first_with_the_prompt_unchanged(self):
        """
        With provider-enforced schema the prompt needs no extra instructions.
        """
        client = StructuredFakeClient()
        client.generate_content("p", response_schema=_SCHEMA)
        self.assertEqual(client.sent, [("schema", "p")])
        self.assertEqual(client.last_structured_mode, "schema")

    def test_no_schema_sends_no_mode(self):
        """
        A plain-text request carries no structured mode.
        """
        client = StructuredFakeClient()
        client.generate_content("p")
        self.assertEqual(client.sent, [(None, "p")])
        self.assertIsNone(client.last_structured_mode)

    def test_degrades_schema_to_json_to_prompt_and_remembers(self):
        """
        Each rejected mode falls to the next, and is skipped on later calls.
        """
        client = StructuredFakeClient(rejecting={"fake-model": {"schema", "json"}})
        self.assertEqual(client.generate_content("p", response_schema=_SCHEMA), '{"a": 1}')
        self.assertEqual(self.modes(client), ["schema", "json", "prompt"])
        self.assertEqual(client.last_structured_mode, "prompt")
        client.sent.clear()
        client.generate_content("p", response_schema=_SCHEMA)
        self.assertEqual(self.modes(client), ["prompt"])

    def test_weaker_modes_embed_the_schema_in_the_prompt(self):
        """
        Without enforcement the model can only follow the schema if it reads it.
        """
        client = StructuredFakeClient(rejecting={"fake-model": {"schema"}})
        client.generate_content("p", response_schema=_SCHEMA)
        json_prompt = client.sent[1][1]
        self.assertTrue(json_prompt.startswith("p"))
        self.assertIn("JSON", json_prompt)
        self.assertIn('"additionalProperties": false', json_prompt)

    def test_unsupported_modes_are_skipped_without_a_request(self):
        """
        A provider without a plain JSON mode goes from schema straight to prompt-only.
        """

        class NoJsonMode(StructuredFakeClient):
            """
            Provider with no plain JSON mode.
            """

            SUPPORTED_STRUCTURED_MODES = ("schema", "prompt")

        client = NoJsonMode(rejecting={"fake-model": {"schema"}})
        client.generate_content("p", response_schema=_SCHEMA)
        self.assertEqual(self.modes(client), ["schema", "prompt"])

    def test_default_provider_is_prompt_only(self):
        """
        A provider that declares nothing gets the schema through the prompt.
        """

        class Plain(StructuredFakeClient):
            """
            Provider that keeps the base default.
            """

            SUPPORTED_STRUCTURED_MODES = AIClient.SUPPORTED_STRUCTURED_MODES

        client = Plain()
        client.generate_content("p", response_schema=_SCHEMA)
        self.assertEqual(self.modes(client), ["prompt"])

    def test_memory_is_per_model_and_per_provider(self):
        """
        One model's rejection doesn't degrade another model or provider.
        """

        class OtherProvider(StructuredFakeClient):
            """
            A second provider serving a model with the same name.
            """

        StructuredFakeClient(rejecting={"fake-model": {"schema"}}).generate_content(
            "p", response_schema=_SCHEMA
        )
        other_model = StructuredFakeClient(model="other")
        other_model.generate_content("p", response_schema=_SCHEMA)
        other_provider = OtherProvider()
        other_provider.generate_content("p", response_schema=_SCHEMA)
        self.assertEqual(self.modes(other_model), ["schema"])
        self.assertEqual(self.modes(other_provider), ["schema"])

    def test_unrelated_errors_propagate_without_degrading(self):
        """
        Only a recognised rejection moves to a weaker mode.
        """
        client = StructuredFakeClient()
        with (
            patch.object(client, "_send", side_effect=RuntimeError("boom")),
            self.assertRaises(RuntimeError),
        ):
            client.generate_content("p", response_schema=_SCHEMA)
        self.assertEqual(AIClient._structured_rejected, set())

    def test_prompt_only_rejection_propagates(self):
        """
        There is nothing weaker than prompt-only, so its failure surfaces.
        """
        client = StructuredFakeClient(rejecting={"fake-model": {"schema", "json", "prompt"}})
        with self.assertRaises(_StructureRejectedError):
            client.generate_content("p", response_schema=_SCHEMA)


if __name__ == "__main__":
    unittest.main()

import contextlib
import contextvars
import json
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import ClassVar, Literal, get_args

from app.utils.logger import get_logger

logger = get_logger(__name__)

# Cadence of the "still working" heartbeat during an in-flight generation.
HEARTBEAT_INTERVAL_S = 10.0
# Main-thread poll timeout, kept short so Ctrl+C stays responsive while a blocking
# socket read (which swallows SIGINT, notably on Windows) is in progress.
_INTERRUPT_POLL_S = 0.25

ReasoningLevel = Literal["low", "medium", "high"]
# A bounded default: unbounded reasoning models can burn their whole output
# budget on hidden thinking before emitting the short structured answers this app needs.
DEFAULT_REASONING: ReasoningLevel = "low"
_REASONING_LEVELS: frozenset[str] = frozenset(get_args(ReasoningLevel))

# Structured-output modes, strongest first: provider-enforced JSON schema, plain
# JSON mode, then the schema carried only by the prompt.
StructuredMode = Literal["schema", "json", "prompt"]
STRUCTURED_MODES: tuple[StructuredMode, ...] = get_args(StructuredMode)


class InvalidAIResponseError(Exception):
    """
    The model answered, but its output is unusable; a fresh generation may succeed.
    """


class AIClient(ABC):
    """
    Abstract base class for AI clients
    """

    DEFAULT_MODEL: str | None = None
    LOG_RETENTION_LIMIT = 50
    CACHE_DIR = "__llmcache__"

    # (provider scope, model) pairs that rejected a reasoning level, so repeat
    # calls to a known non-reasoning model skip the failing round trip.
    _reasoning_unsupported: ClassVar[set[tuple[str, str]]] = set()

    # Modes the provider can attach to a request; prompt-only needs no support.
    SUPPORTED_STRUCTURED_MODES: ClassVar[tuple[StructuredMode, ...]] = ("prompt",)
    # (provider scope, model, mode) triples that rejected a structured-output mode.
    _structured_rejected: ClassVar[set[tuple[str, str, str]]] = set()

    last_structured_mode: StructuredMode | None = None

    def generate_content(
        self,
        prompt: str,
        *,
        reasoning: ReasoningLevel | None = None,
        response_schema: dict | None = None,
        **kwargs,
    ) -> str:
        """
        Generate content using the AI service.

        ``reasoning`` picks the provider's thinking depth (None = DEFAULT_REASONING);
        an unknown level raises ValueError before any provider call. ``response_schema``
        (a JSON Schema) asks for JSON output, enforced by the provider when it can
        (see ``_generate_with_structure``). Runs the provider call on a worker thread while the main thread polls on
        a short timeout, so a slow/buffering provider stays interruptible by
        Ctrl+C and emits a heartbeat instead of going silent.
        """
        level = self._resolve_reasoning(reasoning)
        self.last_structured_mode = None
        if response_schema is not None:
            kwargs["response_schema"] = response_schema
        model_name = self.get_model_name()
        start = time.perf_counter()
        done = threading.Event()
        outcome: dict[str, str] = {}
        failure: dict[str, BaseException] = {}

        def _worker() -> None:
            """
            Runs the blocking provider call off the main thread.
            """
            try:
                outcome["text"] = self._generate_content_impl(prompt, reasoning=level, **kwargs)
            except Exception as exc:
                failure["exc"] = exc
            finally:
                done.set()

        # Propagate context so the worker's logs reach the right SSE queue (app/api/sse.py).
        ctx = contextvars.copy_context()
        worker = threading.Thread(target=lambda: ctx.run(_worker), daemon=True)
        worker.start()

        next_heartbeat = HEARTBEAT_INTERVAL_S
        while not done.wait(_INTERRUPT_POLL_S):
            elapsed = time.perf_counter() - start
            if elapsed >= next_heartbeat:
                logger.progress("%s: still working... %.0fs elapsed", model_name, elapsed)
                next_heartbeat += HEARTBEAT_INTERVAL_S

        if "exc" in failure:
            raise failure["exc"]

        response = outcome.get("text", "")
        logger.success(
            "%s: response in %.1fs (%d chars)",
            self._answering_model_name(),
            time.perf_counter() - start,
            len(response),
        )
        self._log_response(prompt, response)
        return response

    @abstractmethod
    def _generate_content_impl(
        self, prompt: str, reasoning: ReasoningLevel | None = None, **kwargs
    ) -> str:
        """
        Actual implementation to generate content using the AI service.
        Must be implemented by subclasses.
        """
        pass

    @staticmethod
    def _resolve_reasoning(reasoning: str | None) -> ReasoningLevel:
        """
        Validates a requested reasoning level, mapping None to DEFAULT_REASONING.
        """
        if reasoning is None:
            return DEFAULT_REASONING
        if reasoning not in _REASONING_LEVELS:
            raise ValueError(
                f"Invalid reasoning level {reasoning!r}; expected one of {sorted(_REASONING_LEVELS)}"
            )
        return reasoning  # type: ignore[return-value]

    def _provider_scope(self) -> str:
        """
        Namespace for the rejection memory, so equal model names on different
        providers are tracked separately. Defaults to the class name.
        """
        return type(self).__name__

    def _is_reasoning_rejected(self, exc: BaseException) -> bool:
        """
        Whether ``exc`` is the provider refusing the reasoning parameter.
        Providers override this; the default recognises nothing.
        """
        return False

    def _generate_with_reasoning(
        self,
        model: str,
        reasoning: str | None,
        send: Callable[[ReasoningLevel | None], str],
    ) -> str:
        """
        Calls ``send`` with the resolved level; if the model rejects it,
        remembers the model and retries once with no level (``send(None)``).
        """
        level = self._resolve_reasoning(reasoning)
        key = (self._provider_scope(), model)
        if key in self._reasoning_unsupported:
            return send(None)
        try:
            return send(level)
        except Exception as exc:
            if not self._is_reasoning_rejected(exc):
                raise
            logger.warning(
                "%s: %s does not support a reasoning level, retrying without it",
                type(self).__name__,
                model,
            )
            self._reasoning_unsupported.add(key)
            return send(None)

    def _is_structured_output_rejected(self, exc: BaseException) -> bool:
        """
        Whether ``exc`` is the provider refusing a structured-output mode.
        Providers override this; the default recognises nothing.
        """
        return False

    @staticmethod
    def _schema_instructions(prompt: str, schema: dict) -> str:
        """
        Appends the schema to the prompt, for modes where the provider does not enforce it.
        """
        return (
            f"{prompt}\n\n# RESPONSE FORMAT\n"
            "Return ONLY a single JSON object, with no text before or after it, "
            "that validates against this JSON Schema:\n"
            f"{json.dumps(schema, indent=2)}\n"
        )

    def _generate_with_structure(
        self,
        model: str,
        prompt: str,
        schema: dict | None,
        send: Callable[[str, StructuredMode | None], str],
    ) -> str:
        """
        Calls ``send(prompt, mode)`` with the strongest supported mode not known
        to be rejected by ``model``, degrading schema -> json -> prompt-only on
        each recognised rejection and remembering it. Without a schema, sends no mode.
        """
        if schema is None:
            return send(prompt, None)
        scope = self._provider_scope()
        candidates: list[StructuredMode] = [
            mode
            for mode in STRUCTURED_MODES
            if (mode == "prompt" or mode in self.SUPPORTED_STRUCTURED_MODES)
            and (scope, model, mode) not in self._structured_rejected
        ]
        for mode in candidates:
            mode_prompt = prompt if mode == "schema" else self._schema_instructions(prompt, schema)
            try:
                text = send(mode_prompt, mode)
            except Exception as exc:
                if mode == "prompt" or not self._is_structured_output_rejected(exc):
                    raise
                logger.warning(
                    "%s: %s does not support %s structured output, degrading",
                    type(self).__name__,
                    model,
                    mode,
                )
                self._structured_rejected.add((scope, model, mode))
                continue
            self.last_structured_mode = mode
            return text
        raise AssertionError("prompt-only mode is always a candidate")

    def _log_response(self, prompt: str, response: str):
        """
        Logs the prompt and response to a local cache file for analysis.
        Maintains a rolling window of the last LOG_RETENTION_LIMIT logs.
        """
        import uuid
        from pathlib import Path

        cache_dir = Path(self.CACHE_DIR)
        cache_dir.mkdir(parents=True, exist_ok=True)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        filepath = cache_dir / f"response_{timestamp}_{unique_id}.log"

        try:
            with filepath.open("w", encoding="utf-8") as f:
                f.write(f"Model: {self.get_model_name()}\n")
                f.write(f"Timestamp: {timestamp}\n")
                f.write("-" * 80 + "\n")
                f.write(f"Prompt:\n{prompt}\n")
                f.write("-" * 80 + "\n")
                f.write(f"Response:\n{response}\n")
                f.write("-" * 80 + "\n")

            # Cleanup old logs, keep last LOG_RETENTION_LIMIT
            files = sorted(cache_dir.glob("response_*.log"))
            if len(files) > self.LOG_RETENTION_LIMIT:
                for old_file in files[: -self.LOG_RETENTION_LIMIT]:
                    with contextlib.suppress(OSError):
                        old_file.unlink()
        except Exception:
            logger.error("Failed to log AI response", exc_info=True)

    def _answering_model_name(self) -> str:
        """
        Name of the model that produced the last response; providers with an
        in-call fallback override it so logs don't credit the primary model.
        """
        return self.get_model_name()

    @abstractmethod
    def get_model_name(self) -> str:
        """
        Get the name/identifier of the current model

        Returns:
            Model name as string
        """
        pass

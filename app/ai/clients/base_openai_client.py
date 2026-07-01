import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import ClassVar

from dotenv import load_dotenv
from openai import BadRequestError, OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.ai.clients.base_client import AIClient
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Per-request timeout, so a stalled model fails fast (the OpenAI SDK default is 600s).
REQUEST_TIMEOUT_S = 90.0

# Reasoning models (e.g. gpt-oss) spend a hidden token budget "thinking" before
# emitting content; without a bound they can exhaust their output tokens with
# no visible answer. "low" is enough for this app's short, structured prompts.
DEFAULT_REASONING_EFFORT = "low"


def _identity(model: str) -> str:
    """Default model-name transform: return the model id unchanged."""
    return model


@dataclass(frozen=True)
class OpenAIProviderConfig:
    """
    Declarative configuration for an OpenAI-compatible provider.

    Providers are pure data (base URL, key env var, headers, model-name display
    transform); all behaviour lives in OpenAIClient. This replaces the previous
    per-provider method-override subclasses (config over inheritance).
    """

    base_url: str
    api_key_env: str
    headers: dict[str, str] = field(default_factory=dict)
    extra_body: dict = field(default_factory=dict)
    # Maps the raw model id to its display name (e.g. strip a ":free" suffix).
    model_name_transform: Callable[[str], str] = _identity


class OpenAIClient(AIClient):
    """
    Client for any OpenAI-compatible provider. Configure a provider by
    subclassing and setting ``CONFIG`` (+ ``DEFAULT_MODEL``) — no method
    overrides needed.

    BYOK transition: instantiate with an explicit ``api_key`` from the user's
    stored credentials. The env-var fallback is DEPRECATED and will be removed
    once every call site supplies an explicit key (target: end of Phase 2).
    """

    CONFIG: OpenAIProviderConfig

    # (base_url, model) pairs that have already rejected reasoning_effort, so
    # repeat calls to a known non-reasoning model skip the failing round trip.
    _reasoning_unsupported: ClassVar[set[tuple[str, str]]] = set()

    def __init__(self, model: str | None = None, api_key: str | None = None):
        """
        Args:
            model: model identifier; defaults to the provider's DEFAULT_MODEL.
            api_key: explicit API key. When None, falls back to the legacy
                env-var lookup with a deprecation notice.
        """
        model = model or self.DEFAULT_MODEL
        if model is None:
            raise ValueError(f"{type(self).__name__} has no model and no DEFAULT_MODEL")

        if api_key is None:
            load_dotenv()
            api_key = os.getenv(self.CONFIG.api_key_env)
            if not api_key:
                logger.warning(
                    "Environment variable %s not set. Client may not work.",
                    self.CONFIG.api_key_env,
                )
            else:
                logger.deprecated(
                    "%s initialised from env var %s. Pass `api_key=` from the user's BYOK store instead.",
                    self.__class__.__name__,
                    self.CONFIG.api_key_env,
                )

        self.client = OpenAI(
            base_url=self.CONFIG.base_url,
            api_key=api_key,
            default_headers=dict(self.CONFIG.headers),
            timeout=REQUEST_TIMEOUT_S,
        )
        self.model = model

    def get_model_name(self) -> str:
        """
        Get the current model name (after the provider's display transform).
        """
        return self.CONFIG.model_name_transform(self.model)

    @retry(
        wait=wait_exponential(multiplier=2, min=1, max=8),
        stop=stop_after_attempt(3),
        before_sleep=lambda rs: logger.progress(
            f"Retrying in {rs.next_action.sleep:.2f}s... (Attempt #{rs.attempt_number})"  # type: ignore[union-attr]
        ),
    )
    def _generate_content_impl(self, prompt: str, **kwargs) -> str:
        """
        Generate content from an OpenAI-compatible API via streaming.

        Streaming surfaces time-to-first-token and returns the accumulated text.
        Accepts optional keyword arguments for the completion call. Reasoning
        models get a bounded ``reasoning_effort`` by default; if the model
        rejects the parameter, the call is transparently retried without it
        (see ``_reasoning_unsupported``).
        """
        extra_body = dict(self.CONFIG.extra_body)
        cache_key = (self.CONFIG.base_url, self.model)
        if cache_key not in self._reasoning_unsupported:
            extra_body.setdefault("reasoning_effort", DEFAULT_REASONING_EFFORT)
        if "extra_body" in kwargs:
            extra_body.update(kwargs.pop("extra_body"))

        model_name = self.get_model_name()
        start = time.perf_counter()

        try:
            try:
                return self._stream_completion(prompt, extra_body, model_name, start, **kwargs)
            except BadRequestError as exc:
                if "reasoning_effort" not in extra_body or "reasoning_effort" not in str(exc):
                    raise
                logger.warning(
                    "%s: %s does not support reasoning_effort, retrying without it",
                    self.__class__.__name__,
                    self.model,
                )
                self._reasoning_unsupported.add(cache_key)
                extra_body = {k: v for k, v in extra_body.items() if k != "reasoning_effort"}
                return self._stream_completion(prompt, extra_body, model_name, start, **kwargs)
        except Exception:
            logger.error(
                "%s: API call failed for model %s after %.1fs",
                self.__class__.__name__,
                self.model,
                time.perf_counter() - start,
                exc_info=True,
            )
            raise

    def _stream_completion(
        self, prompt: str, extra_body: dict, model_name: str, start: float, **kwargs
    ) -> str:
        """
        Sends one streamed completion request and accumulates the text deltas.
        """
        chunks: list[str] = []
        ttft_logged = False

        stream = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            extra_body=extra_body,
            stream=True,
            **kwargs,
        )
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if not delta:
                continue
            if not ttft_logged:
                ttft_logged = True
                logger.progress(
                    "%s: first token after %.1fs", model_name, time.perf_counter() - start
                )
            chunks.append(delta)
        return "".join(chunks)

import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import ClassVar

from dotenv import load_dotenv
from openai import (
    APIConnectionError,
    APIStatusError,
    BadRequestError,
    OpenAI,
    RateLimitError,
)
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.ai.clients.base_client import (
    AIClient,
    InvalidAIResponseError,
    ReasoningLevel,
    StructuredMode,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _response_format(mode: StructuredMode | None, schema: dict | None) -> dict | None:
    """
    The ``response_format`` request field for a structured-output mode, or None.
    """
    if mode == "schema":
        return {
            "type": "json_schema",
            "json_schema": {"name": "response", "schema": schema, "strict": True},
        }
    if mode == "json":
        return {"type": "json_object"}
    return None


# Per-request timeout, so a stalled model fails fast (the OpenAI SDK default is 600s).
REQUEST_TIMEOUT_S = 90.0


def _identity(model: str) -> str:
    """
    Default model-name transform: return the model id unchanged.
    """
    return model


def _is_transient(exc: BaseException) -> bool:
    """
    Whether an API error is worth retrying: connection/timeout, rate limit or a 5xx.
    """
    if isinstance(exc, (APIConnectionError, RateLimitError)):
        return True
    return isinstance(exc, APIStatusError) and exc.status_code >= 500


def _is_schema_validation_failure(exc: APIStatusError) -> bool:
    """
    Whether the provider rejected the model's output for not matching the JSON schema.
    """
    return exc.status_code == 400 and "json_validate_failed" in str(exc).lower()


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
    SUPPORTED_STRUCTURED_MODES: ClassVar[tuple[StructuredMode, ...]] = ("schema", "json", "prompt")

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
        retry=retry_if_exception(_is_transient),
        before_sleep=lambda rs: logger.progress(
            "Retrying in %.2fs... (Attempt #%d)",
            rs.next_action.sleep,  # type: ignore[union-attr]
            rs.attempt_number,
        ),
    )
    def _generate_content_impl(
        self,
        prompt: str,
        reasoning: ReasoningLevel | None = None,
        response_schema: dict | None = None,
        **kwargs,
    ) -> str:
        """
        Generate content from an OpenAI-compatible API via streaming.

        Streaming surfaces time-to-first-token and returns the accumulated text.
        Accepts optional keyword arguments for the completion call. ``reasoning``
        maps to ``reasoning_effort``; a model rejecting it is retried without it
        through the shared flow in AIClient. ``response_schema`` maps to
        ``response_format`` (strict json_schema, then json_object), degrading
        through the shared structured-output flow.
        """
        base_extra_body = dict(self.CONFIG.extra_body)
        if "extra_body" in kwargs:
            base_extra_body.update(kwargs.pop("extra_body"))

        model_name = self.get_model_name()
        start = time.perf_counter()

        def _send_structured(mode_prompt: str, mode: StructuredMode | None) -> str:
            """
            Sends one completion in ``mode`` through the reasoning fallback.
            """
            request_kwargs = dict(kwargs)
            response_format = _response_format(mode, response_schema)
            if response_format is not None:
                request_kwargs["response_format"] = response_format

            def _send(level: ReasoningLevel | None) -> str:
                """
                Streams one completion, with reasoning_effort unless ``level`` is None.
                """
                extra_body = dict(base_extra_body)
                if level is None:
                    extra_body.pop("reasoning_effort", None)
                else:
                    extra_body.setdefault("reasoning_effort", level)
                return self._stream_completion(
                    mode_prompt, extra_body, model_name, start, **request_kwargs
                )

            return self._generate_with_reasoning(self.model, reasoning, _send)

        try:
            return self._generate_with_structure(
                self.model, prompt, response_schema, _send_structured
            )
        except APIStatusError as exc:
            if not _is_schema_validation_failure(exc):
                self._log_failure(start)
                raise
            logger.warning(
                "%s: %s output failed the provider's schema validation",
                self.__class__.__name__,
                self.model,
            )
            raise InvalidAIResponseError(str(exc)) from exc
        except Exception:
            self._log_failure(start)
            raise

    def _log_failure(self, start: float) -> None:
        """
        Logs a failed API call with its elapsed time and traceback.
        """
        logger.error(
            "%s: API call failed for model %s after %.1fs",
            self.__class__.__name__,
            self.model,
            time.perf_counter() - start,
            exc_info=True,
        )

    def _provider_scope(self) -> str:
        """
        Scopes the rejection memory by endpoint, since providers share model names.
        """
        return self.CONFIG.base_url

    def _is_reasoning_rejected(self, exc: BaseException) -> bool:
        """
        OpenAI-compatible providers reject the parameter with a 400 naming it.
        """
        return isinstance(exc, BadRequestError) and "reasoning_effort" in str(exc)

    def _is_structured_output_rejected(self, exc: BaseException) -> bool:
        """
        Providers and routers refuse an unsupported response_format with a 400,
        404 or 422 naming it; an output failing the schema is not a refusal.
        """
        if not isinstance(exc, APIStatusError) or exc.status_code not in (400, 404, 422):
            return False
        message = str(exc).lower().replace("-", " ")
        if "json_validate_failed" in message:
            return False
        markers = ("response_format", "json_schema", "json_object", "structured output")
        return any(marker in message for marker in markers)

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

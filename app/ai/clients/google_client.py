import time
from typing import ClassVar

import httpx
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import ClientError, ServerError
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.ai.clients import AIClient
from app.ai.clients.base_client import ReasoningLevel, StructuredMode
from app.utils.logger import get_logger

logger = get_logger(__name__)

_THINKING_LEVELS: dict[str, types.ThinkingLevel] = {
    "low": types.ThinkingLevel.LOW,
    "medium": types.ThinkingLevel.MEDIUM,
    "high": types.ThinkingLevel.HIGH,
}


def _is_transient(exc: BaseException) -> bool:
    """
    Whether a Gemini call failure is worth retrying: a 5xx, a 429 or a transport failure.
    """
    if isinstance(exc, (ServerError, httpx.TransportError, TimeoutError, ConnectionError)):
        return True
    return isinstance(exc, ClientError) and exc.code == 429


def _warrants_fallback(exc: ServerError | ClientError) -> bool:
    """
    Whether a primary-model failure should switch to FALLBACK_MODEL: a 503 overload or a 429.
    """
    if isinstance(exc, ClientError):
        return exc.code == 429
    return "unavailable" in str(exc).lower()


class GoogleAIClient(AIClient):
    """
    Google AI client implementation for Gemini models.
    """

    DEFAULT_MODEL = "gemini-3.8-flash"

    # Model to switch to, within the same call, when the primary model is
    # overloaded (503 UNAVAILABLE) or rate-limited (429): the free tier's
    # per-minute quota and "high demand" spikes both outlast the retry backoff.
    FALLBACK_MODEL: ClassVar[str] = "gemini-3.5-flash-lite"

    SUPPORTED_STRUCTURED_MODES: ClassVar[tuple[StructuredMode, ...]] = ("schema", "json", "prompt")

    def __init__(self, model: str = DEFAULT_MODEL, api_key: str | None = None):
        """
        Initialise the Google AI client.

        Args:
            model: model name (default DEFAULT_MODEL).
            api_key: explicit API key. When None, falls back to GOOGLE_API_KEY
                env var via genai.Client default — DEPRECATED, will be required
                explicitly once BYOK is wired end-to-end.
        """
        # Mirror the OpenAI-compatible clients' 90s request timeout: without it
        # a stalled call emits heartbeats forever (google-genai wants ms).
        http_options = types.HttpOptions(timeout=90_000)
        if api_key is None:
            load_dotenv()
            self.client = genai.Client(http_options=http_options)
        else:
            self.client = genai.Client(api_key=api_key, http_options=http_options)
        self.model = model
        self._answered_by: str | None = None

    def get_model_name(self) -> str:
        """
        Get the current Gemini model name
        """
        return f"google/{self.model}"

    def _answering_model_name(self) -> str:
        """
        Names the model that actually answered, which is FALLBACK_MODEL after an overload.
        """
        return f"google/{self._answered_by or self.model}"

    @retry(
        wait=wait_exponential(multiplier=2, min=1, max=8),
        stop=stop_after_attempt(3),
        retry=retry_if_exception(_is_transient),
        before_sleep=lambda rs: logger.progress(
            "Google AI service unavailable, retrying in %.2fs... (Attempt #%d)",
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
        Generate content using Google AI Gemini API

        Args:
            prompt: The input prompt for content generation
            reasoning: thinking level (None = the shared default)
            response_schema: JSON Schema for the answer (None = plain text)

        Returns:
            Generated content as string

        Raises:
            Exception: If the Google AI API call fails after retries
        """
        self._answered_by = self.model
        try:
            try:
                return self._generate_on(prompt, self.model, reasoning, response_schema)
            except (ServerError, ClientError) as exc:
                if self.model == self.FALLBACK_MODEL or not _warrants_fallback(exc):
                    raise
                logger.warning(
                    "GoogleAIClient: %s is overloaded or rate-limited (%s), falling back to %s",
                    self.model,
                    exc,
                    self.FALLBACK_MODEL,
                )
                self._answered_by = self.FALLBACK_MODEL
                return self._generate_on(prompt, self.FALLBACK_MODEL, reasoning, response_schema)
        except Exception:
            logger.error("Google AI API call failed", exc_info=True)
            raise

    def _generate_on(
        self,
        prompt: str,
        model: str,
        reasoning: ReasoningLevel | None,
        schema: dict | None = None,
    ) -> str:
        """
        Generates on ``model`` through the shared structured-output and reasoning flows.
        """

        def _send(mode_prompt: str, mode: StructuredMode | None) -> str:
            """
            Sends one request in ``mode`` through the reasoning fallback.
            """
            return self._generate_with_reasoning(
                model,
                reasoning,
                lambda level: self._generate_once(mode_prompt, model, level, mode, schema),
            )

        return self._generate_with_structure(model, prompt, schema, _send)

    def _is_structured_output_rejected(self, exc: BaseException) -> bool:
        """
        Gemini rejects an unsupported JSON mode or schema with a 400 naming the field.
        """
        if not isinstance(exc, ClientError) or exc.code != 400:
            return False
        message = str(exc).lower()
        markers = ("response_json_schema", "response_schema", "response_mime_type", "json mode")
        return any(marker in message for marker in markers)

    def _is_reasoning_rejected(self, exc: BaseException) -> bool:
        """
        Gemini rejects thinking_config on non-thinking models with a 4xx naming it.
        """
        return isinstance(exc, ClientError) and "thinking" in str(exc).lower()

    def _generate_once(
        self,
        prompt: str,
        model: str,
        level: ReasoningLevel | None,
        mode: StructuredMode | None = None,
        schema: dict | None = None,
    ) -> str:
        """
        Streams one request (with a thinking level unless ``level`` is None, and
        JSON output per ``mode``) and returns the accumulated text, logging
        time-to-first-token once.
        """
        # No tools are ever passed, but google-genai >= 2.21 warns on every
        # generate_content call unless AFC is disabled explicitly.
        config = types.GenerateContentConfig(
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
        )
        if level is not None:
            config.thinking_config = types.ThinkingConfig(thinking_level=_THINKING_LEVELS[level])
        if mode in ("schema", "json"):
            config.response_mime_type = "application/json"
        if mode == "schema":
            config.response_json_schema = schema

        model_name = f"google/{model}"
        start = time.perf_counter()
        parts: list[str] = []
        stream = self.client.models.generate_content_stream(
            model=model, contents=prompt, config=config
        )
        for chunk in stream:
            text = chunk.text
            if not text:
                continue
            if not parts:
                logger.progress(
                    "%s: first token after %.1fs", model_name, time.perf_counter() - start
                )
            parts.append(text)
        return "".join(parts)

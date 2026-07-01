from typing import ClassVar

from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import ClientError, ServerError
from tenacity import retry, stop_after_attempt, wait_exponential

from app.ai.clients import AIClient
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Mirrors DEFAULT_REASONING_EFFORT in base_openai_client.py: a bounded thinking
# budget for reasoning-capable Gemini models, so short structured prompts
# don't burn output tokens on hidden chain-of-thought.
DEFAULT_THINKING_LEVEL = types.ThinkingLevel.LOW


class GoogleAIClient(AIClient):
    """
    Google AI client implementation using Gemini models (e.g., Gemini 2.5)
    """

    DEFAULT_MODEL = "gemini-2.5-flash"

    # Model to switch to, within the same call, when the primary model is
    # overloaded (503 UNAVAILABLE) — "high demand" spikes are usually
    # temporary but can outlast the outer retry's backoff window.
    FALLBACK_MODEL: ClassVar[str] = "gemini-3.1-flash-lite"

    # Model names that have already rejected thinking_config, so repeat calls
    # to a known non-thinking model skip the failing round trip.
    _thinking_unsupported: ClassVar[set[str]] = set()

    def __init__(self, model: str = DEFAULT_MODEL, api_key: str | None = None):
        """
        Initialise the Google AI client.

        Args:
            model: model name (default 'gemini-2.5-flash').
            api_key: explicit API key. When None, falls back to GOOGLE_API_KEY
                env var via genai.Client default — DEPRECATED, will be required
                explicitly once BYOK is wired end-to-end.
        """
        if api_key is None:
            load_dotenv()
            self.client = genai.Client()
        else:
            self.client = genai.Client(api_key=api_key)
        self.model = model

    def get_model_name(self) -> str:
        """
        Get the current Gemini model name
        """
        return f"google/{self.model}"

    @retry(
        wait=wait_exponential(multiplier=2, min=1, max=8),
        stop=stop_after_attempt(3),
        before_sleep=lambda rs: logger.progress(
            f"Google AI service unavailable, retrying in {rs.next_action.sleep:.2f}s... (Attempt #{rs.attempt_number})"  # type: ignore[union-attr]
        ),
    )
    def _generate_content_impl(self, prompt: str, **kwargs) -> str:
        """
        Generate content using Google AI Gemini API

        Args:
            prompt: The input prompt for content generation

        Returns:
            Generated content as string

        Raises:
            Exception: If the Google AI API call fails after retries
        """
        try:
            try:
                return self._generate_with_thinking_fallback(prompt, self.model)
            except ServerError as exc:
                if self.model == self.FALLBACK_MODEL or "unavailable" not in str(exc).lower():
                    raise
                logger.warning(
                    "GoogleAIClient: %s is overloaded (%s), falling back to %s",
                    self.model,
                    exc,
                    self.FALLBACK_MODEL,
                )
                result = self._generate_with_thinking_fallback(prompt, self.FALLBACK_MODEL)
                self.model = self.FALLBACK_MODEL
                return result
        except Exception:
            logger.error("Google AI API call failed", exc_info=True)
            raise

    def _generate_with_thinking_fallback(self, prompt: str, model: str) -> str:
        """
        Generates content on ``model``, retrying once without thinking_config
        if the model rejects it.
        """
        try:
            return self._generate_once(prompt, model, with_thinking_config=True)
        except ClientError as exc:
            if model in self._thinking_unsupported or "thinking" not in str(exc).lower():
                raise
            logger.warning(
                "GoogleAIClient: %s does not support thinking_config, retrying without it",
                model,
            )
            self._thinking_unsupported.add(model)
            return self._generate_once(prompt, model, with_thinking_config=False)

    def _generate_once(self, prompt: str, model: str, with_thinking_config: bool) -> str:
        """
        Sends one generate_content request, optionally with a bounded
        thinking_config, and returns the response text.
        """
        config = None
        if with_thinking_config and model not in self._thinking_unsupported:
            config = types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_level=DEFAULT_THINKING_LEVEL)
            )

        request_kwargs = {"config": config} if config is not None else {}
        response = self.client.models.generate_content(
            model=model, contents=prompt, **request_kwargs
        )
        return response.text or ""

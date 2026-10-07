from typing import ClassVar

from app.ai.clients.base_client import StructuredMode
from app.ai.clients.base_openai_client import OpenAIClient, OpenAIProviderConfig


class ZaiClient(OpenAIClient):
    """
    Z.AI client (GLM models). Requires ZAI_API_KEY.

    GLM-4.7-Flash and GLM-4.5-Flash are free; every other model is billed and answers 429 when
    the account has no balance. A request the provider refuses with 429 or 5xx (the free models
    also answer 429 when overloaded) is repeated on GLM-4.5-Flash. Z.AI documents only plain JSON
    mode (no json_schema), so the schema travels in the prompt.
    """

    DEFAULT_MODEL = "glm-4.7-flash"
    FALLBACK_MODEL = "glm-4.5-flash"
    SUPPORTED_STRUCTURED_MODES: ClassVar[tuple[StructuredMode, ...]] = ("json", "prompt")
    CONFIG = OpenAIProviderConfig(
        base_url="https://api.z.ai/api/paas/v4/",
        api_key_env="ZAI_API_KEY",
    )

from typing import ClassVar

from app.ai.clients.base_client import StructuredMode
from app.ai.clients.base_openai_client import OpenAIClient, OpenAIProviderConfig


class OllamaClient(OpenAIClient):
    """
    Ollama Cloud client (open-weight models hosted by Ollama). Requires OLLAMA_API_KEY.

    The free plan covers a small set of models; any other answers 402. The API accepts a
    json_schema but does not apply it, so only plain JSON mode is used and the schema travels in
    the prompt.
    """

    DEFAULT_MODEL = "nemotron-3-super"
    SUPPORTED_STRUCTURED_MODES: ClassVar[tuple[StructuredMode, ...]] = ("json", "prompt")
    CONFIG = OpenAIProviderConfig(
        base_url="https://ollama.com/v1",
        api_key_env="OLLAMA_API_KEY",
    )

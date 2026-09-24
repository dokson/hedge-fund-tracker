from app.ai.clients.base_openai_client import OpenAIClient, OpenAIProviderConfig


class GroqClient(OpenAIClient):
    """
    Groq client (open-weight models hosted on Groq). Requires GROQ_API_KEY.
    """

    DEFAULT_MODEL = "openai/gpt-oss-120b"
    CONFIG = OpenAIProviderConfig(
        base_url="https://api.groq.com/openai/v1",
        api_key_env="GROQ_API_KEY",
    )

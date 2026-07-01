from app.ai.clients.base_openai_client import OpenAIClient, OpenAIProviderConfig


class GroqClient(OpenAIClient):
    """
    Groq client (Llama and other hosted models). Requires GROQ_API_KEY.
    """

    DEFAULT_MODEL = "llama-3.1-8b-instant"
    CONFIG = OpenAIProviderConfig(
        base_url="https://api.groq.com/openai/v1",
        api_key_env="GROQ_API_KEY",
    )

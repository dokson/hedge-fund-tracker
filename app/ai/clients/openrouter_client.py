from app.ai.clients.base_openai_client import OpenAIClient


class OpenRouterClient(OpenAIClient):
    """
    OpenRouter client implementation using various available models (e.g., DeepSeek)
    """
    DEFAULT_MODEL = "xiaomi/mimo-v2-flash:free"


    def __init__(self, model: str = DEFAULT_MODEL):
        """
        Initializes the OpenRouter client.
        Requires OPENROUTER_API_KEY to be set in the environment.
        """
        super().__init__(model)


    def get_model_name(self) -> str:
        """
        Get the current OpenRouter model name
        """
        return self.model.removesuffix(":free")


    def get_base_url(self) -> str:
        """
        Returns the base URL for the OpenRouter API.
        """
        return "https://openrouter.ai/api/v1"


    def get_api_key_env_var(self) -> str:
        """
        Returns the name of the environment variable for the OpenRouter API key.
        """
        return "OPENROUTER_API_KEY"


    def get_headers(self) -> dict:
        """
        Returns the recommended headers for OpenRouter.
        """
        return {
            "HTTP-Referer": "https://github.com/dokson/hedge-fund-tracker",
            "X-Title": "Hedge Fund Tracker"
        }


    def get_extra_body(self) -> dict:
        """
        Returns extra body parameters.
        Some providers (like Venice) might be sensitive to these even if empty.
        """
        return {}

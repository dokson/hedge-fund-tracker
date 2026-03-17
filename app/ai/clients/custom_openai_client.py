from app.ai.clients.base_openai_client import OpenAIClient
from dotenv import load_dotenv
import os


class CustomOpenAIClient(OpenAIClient):
    """
    Custom OpenAI-compatible client for any API endpoint that supports the OpenAI protocol.
    Users can specify their own base URL and API key.
    """
    DEFAULT_MODEL = "custom-model"

    def __init__(self, model: str = DEFAULT_MODEL):
        """
        Initializes the custom OpenAI-compatible client.
        Requires CUSTOM_OPENAI_URL and CUSTOM_OPENAI_KEY to be set in the environment.
        """
        load_dotenv()
        base_url = os.getenv("CUSTOM_OPENAI_URL")
        api_key = os.getenv("CUSTOM_OPENAI_KEY")
        
        if not base_url:
            print("🚨 WARNING: CUSTOM_OPENAI_URL not set. Custom client may not work.")
        
        if not api_key:
            print("🚨 WARNING: CUSTOM_OPENAI_KEY not set. Custom client may not work.")

        self.client = self._create_client(base_url, api_key)
        self.model = model

    def _create_client(self, base_url: str | None, api_key: str | None):
        """
        Creates the OpenAI client with custom configuration.
        """
        from openai import OpenAI
        return OpenAI(
            base_url=base_url or "",
            api_key=api_key or "",
            default_headers=self.get_headers()
        )

    def get_base_url(self) -> str:
        """
        Returns the custom base URL.
        """
        return os.getenv("CUSTOM_OPENAI_URL", "")

    def get_api_key_env_var(self) -> str:
        """
        Returns the environment variable name for the custom API key.
        """
        return "CUSTOM_OPENAI_KEY"

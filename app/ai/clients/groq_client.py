from app.ai.clients.base_openai_client import OpenAIClient


class GroqClient(OpenAIClient):
    """
    Groq AI client implementation using available models (e.g., Llama)
    """
    DEFAULT_MODEL = "llama-3.3-70b-versatile"


    def __init__(self, model: str = DEFAULT_MODEL):
        """
        Initializes the Groq client.
        Requires GROQ_API_KEY to be set in the environment.
        """
        super().__init__(model)


    def get_base_url(self) -> str:
        """
        Returns the base URL for the Groq API.
        """
        return "https://api.groq.com/openai/v1"


    def get_api_key_env_var(self) -> str:
        """
        Returns the name of the environment variable for the Groq API key.
        """
        return "GROQ_API_KEY"

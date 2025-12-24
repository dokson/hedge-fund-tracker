from app.ai.clients.base_openai_client import OpenAIClient


class HuggingFaceClient(OpenAIClient):
    """
    Hugging Face Inference Providers client implementation using their OpenAI-compatible API.
    """
    DEFAULT_MODEL = "deepseek-ai/DeepSeek-R1"


    def __init__(self, model: str = DEFAULT_MODEL):
        """
        Initializes the Hugging Face client.
        Requires HF_TOKEN to be set in the environment.
        """
        super().__init__(model)


    def get_base_url(self) -> str:
        """
        Returns the base URL for the Hugging Face Inference API.
        """
        return "https://router.huggingface.co/v1/"


    def get_model_name(self) -> str:
        """
        Get the current Hugging Face model name (removing provider suffixes).
        """
        return self.model.split(':')[0]


    def get_api_key_env_var(self) -> str:
        """
        Returns the name of the environment variable for the Hugging Face token.
        """
        return "HF_TOKEN"

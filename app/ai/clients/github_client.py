from app.ai.clients.base_openai_client import OpenAIClient


class GitHubClient(OpenAIClient):
    """
    GitHub Models client implementation using the Azure AI Inference API.
    """
    DEFAULT_MODEL = "openai/gpt-5-mini"


    def __init__(self, model: str = DEFAULT_MODEL):
        """
        Initializes the GitHub Models client.
        Requires GITHUB_TOKEN to be set in the environment.
        """
        super().__init__(model)


    def get_base_url(self) -> str:
        """
        Returns the base URL for the GitHub Models API.
        """
        return "https://models.github.ai/inference"


    def get_api_key_env_var(self) -> str:
        """
        Returns the name of the environment variable for the GitHub token.
        """
        return "GITHUB_TOKEN"

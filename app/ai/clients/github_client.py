from app.ai.clients.base_openai_client import OpenAIClient, OpenAIProviderConfig


class GitHubClient(OpenAIClient):
    """
    GitHub Models client (Azure AI Inference, OpenAI-compatible). Requires GITHUB_TOKEN.
    """

    DEFAULT_MODEL = "xai/grok-3-mini"
    CONFIG = OpenAIProviderConfig(
        base_url="https://models.github.ai/inference",
        api_key_env="GITHUB_TOKEN",
    )

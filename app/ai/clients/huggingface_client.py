from app.ai.clients.base_openai_client import OpenAIClient, OpenAIProviderConfig


class HuggingFaceClient(OpenAIClient):
    """
    Hugging Face Inference Providers (OpenAI-compatible). Requires HF_TOKEN.

    The display name strips any ``:provider`` routing suffix from the model id.
    """

    DEFAULT_MODEL = "deepseek-ai/DeepSeek-R1"
    CONFIG = OpenAIProviderConfig(
        base_url="https://router.huggingface.co/v1/",
        api_key_env="HF_TOKEN",
        model_name_transform=lambda m: m.split(":")[0],
    )

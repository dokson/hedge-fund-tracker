from app.ai.clients.base_openai_client import OpenAIClient, OpenAIProviderConfig


class OpenRouterClient(OpenAIClient):
    """
    OpenRouter client (aggregates many providers). Requires OPENROUTER_API_KEY.

    Sends the recommended attribution headers; the display name drops the
    ``:free`` tier suffix.
    """

    DEFAULT_MODEL = "xiaomi/mimo-v2-flash:free"
    CONFIG = OpenAIProviderConfig(
        base_url="https://openrouter.ai/api/v1",
        api_key_env="OPENROUTER_API_KEY",
        headers={
            "HTTP-Referer": "https://github.com/dokson/hedge-fund-tracker",
            "X-Title": "Hedge Fund Tracker",
        },
        model_name_transform=lambda m: m.removesuffix(":free"),
    )

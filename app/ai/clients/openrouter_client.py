from app.ai.clients import AIClient
from dotenv import load_dotenv
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
import ast
import os
import re


class OpenRouterClient(AIClient):
    """
    OpenRouter client implementation using various available models.
    """
    DEFAULT_MODEL = "deepseek/deepseek-chat-v3.1:free"


    def __init__(self, model: str = DEFAULT_MODEL):
        """
        Initializes the OpenRouter client.
        Requires OPENROUTER_API_KEY to be set in the environment.
        """
        load_dotenv()
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"),
        )
        self.model = model

    def get_model_name(self) -> str:
        """
        Get the current OpenRouter model name
        """
        return self.model

    @retry(
        wait=wait_exponential(multiplier=2, min=1, max=8),
        stop=stop_after_attempt(3),
        before_sleep=lambda rs: print(
            f"⏳ Retrying in {rs.next_action.sleep:.2f}s... (Attempt #{rs.attempt_number})")
    )
    def generate_content(self, prompt: str) -> str:
        """
        Generate content using OpenRouter API
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            dict_match = re.search(r"\{.*\}", str(e))
            if dict_match:
                error_data = ast.literal_eval(dict_match.group(0))
                if 'error' in error_data and isinstance(error_data['error'], dict):
                    code = error_data['error'].get('code')
                    message = error_data['error'].get('message')
                    if code and message:
                        error_message = f"error code {code}: {message}"
                        print(f"❌ ERROR - OpenRouter API failed with {error_message}")
                        raise Exception(error_message) from e
                else:
                    raise Exception(str(e))

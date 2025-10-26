from abc import abstractmethod
from app.ai.clients.base_client import AIClient
from dotenv import load_dotenv
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
import os


class OpenAIClient(AIClient):
    """
    Abstract base class for AI clients that are compatible with the OpenAI API.
    Subclasses must implement `get_base_url` and `get_api_key_env_var`.
    """

    def __init__(self, model: str):
        """
        Initializes the OpenAI-compatible client.
        """
        load_dotenv()
        api_key = os.getenv(self.get_api_key_env_var())
        if not api_key:
            print(f"🚨 WARNING: Environment variable {self.get_api_key_env_var()} not set. Client may not work.")

        self.client = OpenAI(
            base_url=self.get_base_url(),
            api_key=api_key,
        )
        self.model = model


    @abstractmethod
    def get_base_url(self) -> str:
        """
        Returns the base URL for the API.
        """
        pass


    @abstractmethod
    def get_api_key_env_var(self) -> str:
        """
        Returns the name of the environment variable for the API key.
        """
        pass


    def get_model_name(self) -> str:
        """
        Get the current model name.
        """
        return self.model


    @retry(
        wait=wait_exponential(multiplier=2, min=1, max=8),
        stop=stop_after_attempt(3),
        before_sleep=lambda rs: print(f"⏳ Retrying in {rs.next_action.sleep:.2f}s... (Attempt #{rs.attempt_number})")
    )
    def generate_content(self, prompt: str) -> str:
        """
        Generate content using an OpenAI-compatible API.
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            print(f"❌ ERROR - {self.__class__.__name__}: API call failed for model {self.model}: {e}")
            raise

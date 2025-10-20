from app.ai.clients import AIClient
from dotenv import load_dotenv
from groq import Groq
from tenacity import retry, stop_after_attempt, wait_exponential


class GroqClient(AIClient):
    """
    Groq AI client implementation using available models (e.g., Llama)
    """
    DEFAULT_MODEL = "llama-3.3-70b-versatile"


    def __init__(self, model: str = DEFAULT_MODEL):
        """
        Initializes the Groq client.
        Requires GROQ_API_KEY to be set in the environment.
        """
        load_dotenv()
        self.client = Groq()
        self.model = model


    def get_model_name(self) -> str:
        """
        Get the current Groq model name
        """
        return self.model


    @retry(
        wait=wait_exponential(multiplier=2, min=1, max=8),
        stop=stop_after_attempt(3),
        before_sleep=lambda rs: print(f"⏳ Retrying in {rs.next_action.sleep:.2f}s... (Attempt #{rs.attempt_number})")
    )
    def generate_content(self, prompt: str) -> str:
        """
        Generate content using Groq API

        Args:
            prompt: The input prompt for content generation

        Returns:
            Generated content as string

        Raises:
            Exception: If the Groq API call fails after retries
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
            try:
                message = e.body.get('error', {}).get('message', str(e))
            except (AttributeError, KeyError):
                message = str(e)

            print(f"❌ ERROR - Groq API: {message}")
            raise Exception(message) from e

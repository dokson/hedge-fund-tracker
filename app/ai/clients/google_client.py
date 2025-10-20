from app.ai.clients import AIClient
from dotenv import load_dotenv
from google import genai
from tenacity import retry, stop_after_attempt, wait_exponential


class GoogleAIClient(AIClient):
    """
    Google AI client implementation using Gemini models
    """
    DEFAULT_MODEL = 'gemini-2.5-flash'


    def __init__(self, model: str = DEFAULT_MODEL):
        load_dotenv()
        self.client = genai.Client()
        self.model = model


    def get_model_name(self) -> str:
        """
        Get the current Gemini model name
        """
        return f"google/{self.model}"


    @retry(
        wait=wait_exponential(multiplier=2, min=1, max=8),
        stop=stop_after_attempt(3),
        before_sleep=lambda rs: print(f"Google AI service unavailable, retrying in {rs.next_action.sleep:.2f}s... (Attempt #{rs.attempt_number})")
    )
    def generate_content(self, prompt: str) -> str:
        """
        Generate content using Google AI Gemini API
        
        Args:
            prompt: The input prompt for content generation
            
        Returns:
            Generated content as string
            
        Raises:
            Exception: If the Google AI API call fails after retries
        """
        try:
            response = self.client.models.generate_content(model=self.model, contents=prompt)
            return response.text
        except Exception as e:
            print(f"❌ ERROR: Google AI API call failed: {e}")
            raise

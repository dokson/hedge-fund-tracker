from abc import ABC, abstractmethod


class AIClient(ABC):
    """
    Abstract base class for AI clients
    """
    DEFAULT_MODEL: str | None = None


    @abstractmethod
    def generate_content(self, prompt: str) -> str:
        """
        Generate content using the AI service
        
        Args:
            prompt: The input prompt for content generation
            
        Returns:
            Generated content as string
            
        Raises:
            Exception: If the AI service call fails
        """
        pass


    @abstractmethod
    def get_model_name(self) -> str:
        """
        Get the name/identifier of the current model
        
        Returns:
            Model name as string
        """
        pass

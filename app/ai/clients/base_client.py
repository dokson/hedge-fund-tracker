import contextlib
from abc import ABC, abstractmethod


class AIClient(ABC):
    """
    Abstract base class for AI clients
    """

    DEFAULT_MODEL: str | None = None
    LOG_RETENTION_LIMIT = 50
    CACHE_DIR = "__llmcache__"

    def generate_content(self, prompt: str, **kwargs) -> str:
        """
        Generate content using the AI service.
        This is a template method that handles logging and delegation to the implementation.
        """
        response = self._generate_content_impl(prompt, **kwargs)
        self._log_response(prompt, response)
        return response

    @abstractmethod
    def _generate_content_impl(self, prompt: str, **kwargs) -> str:
        """
        Actual implementation to generate content using the AI service.
        Must be implemented by subclasses.
        """
        pass

    def _log_response(self, prompt: str, response: str):
        """
        Logs the prompt and response to a local cache file for analysis.
        Maintains a rolling window of the last LOG_RETENTION_LIMIT logs.
        """
        import time
        import uuid
        from pathlib import Path

        cache_dir = Path(self.CACHE_DIR)
        cache_dir.mkdir(parents=True, exist_ok=True)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        filepath = cache_dir / f"response_{timestamp}_{unique_id}.log"

        try:
            with filepath.open("w", encoding="utf-8") as f:
                f.write(f"Model: {self.get_model_name()}\n")
                f.write(f"Timestamp: {timestamp}\n")
                f.write("-" * 80 + "\n")
                f.write(f"Prompt:\n{prompt}\n")
                f.write("-" * 80 + "\n")
                f.write(f"Response:\n{response}\n")
                f.write("-" * 80 + "\n")

            # Cleanup old logs, keep last LOG_RETENTION_LIMIT
            files = sorted(cache_dir.glob("response_*.log"))
            if len(files) > self.LOG_RETENTION_LIMIT:
                for old_file in files[: -self.LOG_RETENTION_LIMIT]:
                    with contextlib.suppress(OSError):
                        old_file.unlink()
        except Exception as e:
            print(f"⚠️ Warning: Failed to log AI response: {e}")

    @abstractmethod
    def get_model_name(self) -> str:
        """
        Get the name/identifier of the current model

        Returns:
            Model name as string
        """
        pass

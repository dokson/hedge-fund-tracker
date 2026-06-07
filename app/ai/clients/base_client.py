import contextlib
import contextvars
import threading
import time
from abc import ABC, abstractmethod

from app.utils.logger import get_logger

logger = get_logger(__name__)

# Cadence of the "still working" heartbeat during an in-flight generation.
HEARTBEAT_INTERVAL_S = 10.0
# Main-thread poll timeout, kept short so Ctrl+C stays responsive while a blocking
# socket read (which swallows SIGINT, notably on Windows) is in progress.
_INTERRUPT_POLL_S = 0.25


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

        Runs the provider call on a worker thread while the main thread polls on
        a short timeout, so a slow/buffering provider stays interruptible by
        Ctrl+C and emits a heartbeat instead of going silent.
        """
        model_name = self.get_model_name()
        start = time.perf_counter()
        done = threading.Event()
        outcome: dict[str, str] = {}
        failure: dict[str, BaseException] = {}

        def _worker() -> None:
            """
            Runs the blocking provider call off the main thread.
            """
            try:
                outcome["text"] = self._generate_content_impl(prompt, **kwargs)
            except Exception as exc:
                failure["exc"] = exc
            finally:
                done.set()

        # Propagate context so the worker's logs reach the right SSE queue (app/api/sse.py).
        ctx = contextvars.copy_context()
        worker = threading.Thread(target=lambda: ctx.run(_worker), daemon=True)
        worker.start()

        next_heartbeat = HEARTBEAT_INTERVAL_S
        while not done.wait(_INTERRUPT_POLL_S):
            elapsed = time.perf_counter() - start
            if elapsed >= next_heartbeat:
                logger.progress("%s: still working... %.0fs elapsed", model_name, elapsed)
                next_heartbeat += HEARTBEAT_INTERVAL_S

        if "exc" in failure:
            raise failure["exc"]

        response = outcome.get("text", "")
        logger.success(
            "%s: response in %.1fs (%d chars)",
            model_name,
            time.perf_counter() - start,
            len(response),
        )
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
        except Exception:
            logger.error("Warning: Failed to log AI response", exc_info=True)

    @abstractmethod
    def get_model_name(self) -> str:
        """
        Get the name/identifier of the current model

        Returns:
            Model name as string
        """
        pass

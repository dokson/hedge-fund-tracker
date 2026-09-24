import json
import re

from app.utils.logger import get_logger, log_safe

logger = get_logger(__name__)

_JSON_FENCE_RE = re.compile(r"```(?:\s*json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def _reject_constant(name: str) -> None:
    """
    Refuses NaN/Infinity, which Python's json module accepts but JSON does not.
    """
    raise ValueError(f"non-finite JSON constant {name}")


class ResponseParser:
    """
    Utility class for parsing JSON objects from LLM responses.
    """

    @staticmethod
    def parse_json(response_text: str) -> dict:
        """
        Parses the JSON object in an LLM response, or returns {} when there is none.

        Provider-enforced output is a bare object; the fence and outermost-brace
        fallbacks only serve prompt-only answers that wrap it in text.
        """
        text = response_text.strip()
        candidates = [text]
        fences = _JSON_FENCE_RE.findall(text)
        if fences:
            candidates.append(fences[-1].strip())
        start, end = text.find("{"), text.rfind("}")
        if 0 <= start < end:
            candidates.append(text[start : end + 1])

        for candidate in candidates:
            try:
                decoded = json.loads(candidate, parse_constant=_reject_constant)
            except ValueError:
                continue
            if isinstance(decoded, dict):
                return decoded

        logger.error(
            "Could not find a JSON object in response: %s...",
            log_safe(response_text[:200], max_len=200),
        )
        return {}

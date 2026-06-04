"""
CSV-backed data-access layer, split into cohesive submodules:

- ``quarters`` — quarter discovery + 13F/fund-data loaders
- ``stocks``   — stocks.csv CRUD, the stocks lock, and ticker-change cascades
- ``funds``    — hedge-fund add/delete/restore and their CSVs

This package module is the canonical namespace: it owns the shared constants
(``DB_FOLDER`` and the ``*_FILE`` names), the path-safety helpers, and the
in-process lock primitive, then re-exports every public function so existing
imports (``from app.database import X``) keep working unchanged.

``DB_FOLDER`` lives here on purpose — tests monkeypatch
``app.database.DB_FOLDER`` to redirect I/O at a temp dir, so submodules
must read it as ``_db.DB_FOLDER`` (call-time attribute access) rather than
binding a local copy.
"""

import os
import threading
from pathlib import Path

import pandas as pd

from app.ai.clients import (
    GitHubClient,
    GoogleAIClient,
    GroqClient,
    HuggingFaceClient,
    OpenRouterClient,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

_stocks_thread_lock = threading.Lock()


DB_FOLDER = "./database"
HEDGE_FUNDS_FILE = "hedge_funds.csv"
EXCLUDED_HEDGE_FUNDS_FILE = "excluded_hedge_funds.csv"
LATEST_SCHEDULE_FILINGS_FILE = "non_quarterly.csv"
MODELS_FILE = "models.csv"
SECTOR_HIERARCHY_FILE = "sector_hierarchy.csv"
STOCKS_FILE = "stocks.csv"


def _get_db_root() -> Path:
    """
    Return the resolved Path of DB_FOLDER. Supports dynamic changes (e.g. tests).
    """
    try:
        return Path(DB_FOLDER).resolve()
    except Exception:
        return Path().resolve()


def _safe_db_join(*segments: str) -> Path:
    """
    Safely join segments to DB_FOLDER and verify boundary.

    Each segment is validated via os.path.basename() — the CodeQL-recognised
    sanitizer for py/path-injection.  If basename(s) != s, the segment contained
    a path separator and is rejected.  Only the validated names are joined to the
    root, so no raw user input appears in the path construction.
    """
    root = _get_db_root()
    safe: list[str] = []
    for s in segments:
        clean = os.path.basename(s)  # noqa: PTH119 — CodeQL-recognised sanitizer for py/path-injection
        if not clean or clean in (".", "..") or clean != s:
            raise ValueError(f"Unsafe path segment: {s!r}")
        if ":" in clean or "\x00" in clean:
            raise ValueError(f"Unsafe path segment: {s!r}")
        safe.append(clean)

    resolved = root.joinpath(*safe).resolve()

    # Belt-and-suspenders boundary check
    if not resolved.is_relative_to(root):
        raise ValueError(f"Path traversal detected: {resolved}")

    return resolved


def load_models(filepath: str | None = None) -> list:
    """
    Loads AI models from the file (models.csv).

    Returns:
        list: A list of dictionaries, each representing an AI model with the 'client' key holding the corresponding client class.
    """
    if filepath is None:
        filepath = str(Path(DB_FOLDER) / MODELS_FILE)
    client_map = {
        "GitHub": GitHubClient,
        "Google": GoogleAIClient,
        "Groq": GroqClient,
        "HuggingFace": HuggingFaceClient,
        "OpenRouter": OpenRouterClient,
    }
    try:
        df = pd.read_csv(filepath, keep_default_na=False)
        df["Client"] = df["Client"].map(client_map)
        return df.to_dict("records")
    except Exception:
        logger.error("while reading models from '%s'", filepath, exc_info=True)
        return []


# Re-export every public function so `from app.database import X` keeps working.
# Imported last: submodules do `import app.database as _db` and read the
# constants/helpers above at call time, so the partially-initialised package is fine.
from app.database.funds import *  # noqa: E402,F401,F403
from app.database.quarters import *  # noqa: E402,F401,F403
from app.database.stocks import *  # noqa: E402,F401,F403

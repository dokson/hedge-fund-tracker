"""
Single source-of-truth for the application version.

The canonical value lives in `app/frontend/package.json`; this helper reads it
at import time so the backend (e.g. /health, log lines, AI prompt metadata)
agrees with whatever the frontend bundle reports.

The lookup is best-effort: a missing or malformed file falls back to "0.0.0"
so a stripped-down deployment (no frontend artefacts) still boots.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_PACKAGE_JSON = Path(__file__).resolve().parent.parent / "frontend" / "package.json"


@lru_cache(maxsize=1)
def get_version() -> str:
    """
    Returns the application version as declared in app/frontend/package.json.

    Cached: the file is read once per process.
    """
    try:
        with _PACKAGE_JSON.open(encoding="utf-8") as f:
            data = json.load(f)
        version = data.get("version")
        if isinstance(version, str) and version.strip():
            return version.strip()
    except (OSError, json.JSONDecodeError):
        pass
    return "0.0.0"


__version__ = get_version()

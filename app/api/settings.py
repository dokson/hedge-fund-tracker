"""
Runtime settings endpoints under /api/settings: read and overwrite the project
``.env`` file (used by the AI Settings page to manage provider keys locally).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.api.paths import ENV_FILE
from app.patterns import ENV_KEY_RE

router = APIRouter(tags=["settings"])


@router.get("/api/settings/env")
def get_env() -> dict[str, str]:
    """Return the parsed key/value pairs from the .env file (empty if absent)."""
    if not ENV_FILE.exists():
        return {}
    result: dict[str, str] = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip()
    return result


@router.put("/api/settings/env")
async def put_env(request: Request) -> dict[str, bool]:
    """Overwrite the .env file from a JSON object of key/value pairs.

    Args:
        request: Request whose JSON body maps env var names to values.

    Returns:
        ``{"ok": True}`` on success.

    Raises:
        HTTPException: 422 if the body isn't a flat object of valid env names to
            string values, or if any value contains a newline (which would inject
            extra `.env` lines).
    """
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="Body must be a JSON object")

    lines = []
    for key, value in data.items():
        if not isinstance(key, str) or not ENV_KEY_RE.match(key):
            raise HTTPException(status_code=422, detail=f"Invalid env var name: {key!r}")
        if not isinstance(value, str):
            raise HTTPException(status_code=422, detail=f"Value for {key!r} must be a string")
        if "\n" in value or "\r" in value:
            raise HTTPException(status_code=422, detail=f"Value for {key!r} contains a newline")
        lines.append(f"{key}={value}")

    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"ok": True}

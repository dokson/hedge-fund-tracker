"""
Runtime settings endpoints under /api/settings: read and overwrite the project
``.env`` file (used by the AI Settings page to manage provider keys locally).
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.paths import ENV_FILE

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
    """
    data: dict = await request.json()
    lines = [f"{k}={v}" for k, v in data.items()]
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"ok": True}

"""
Runtime settings endpoints under /api/settings: read and update the provider
API keys held in the project ``.env`` file (used by the AI Settings page).

Only the provider keys in ``MANAGED_ENV_KEYS`` cross the HTTP boundary. The
deployment secrets that share the file — the KEK, the database password, the
token-signing secrets — are never read out to a browser and never writable
over HTTP, so an XSS payload or a leaked DevTools log can't reach them.
"""

from __future__ import annotations

from typing import Final

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.paths import ENV_FILE
from app.auth.dependencies import require_local_or_superuser
from app.patterns import ENV_KEY_RE

# Provider credentials the AI Settings page owns. Everything else in .env is
# deployment configuration and stays server-side.
MANAGED_ENV_KEYS: Final = frozenset(
    {
        "GOOGLE_API_KEY",
        "GROQ_API_KEY",
        "HF_TOKEN",
        "OPENROUTER_API_KEY",
        "OPENFIGI_API_KEY",
        "FMP_API_KEY",
    }
)

# .env holds every provider secret: operator-only in a production posture.
router = APIRouter(tags=["settings"], dependencies=[Depends(require_local_or_superuser)])


def _parse_env_line(line: str) -> tuple[str, str] | None:
    """
    Split a dotenv line into a key/value pair, or None for comments and blanks.
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    key, _, value = stripped.partition("=")
    return key.strip(), value.strip()


@router.get("/api/settings/env")
def get_env() -> dict[str, str]:
    """Return the managed provider keys from the .env file (empty if absent)."""
    if not ENV_FILE.exists():
        return {}
    result: dict[str, str] = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        pair = _parse_env_line(line)
        if pair and pair[0] in MANAGED_ENV_KEYS:
            result[pair[0]] = pair[1]
    return result


@router.put("/api/settings/env")
async def put_env(request: Request) -> dict[str, bool]:
    """Merge managed provider keys into the .env file.

    Unmanaged lines — deployment secrets, comments, formatting — are preserved
    verbatim, so a client that only knows about provider keys can never drop
    MASTER_KEY and render every stored API key undecryptable. An empty value
    removes the key.

    Args:
        request: Request whose JSON body maps managed env var names to values.

    Returns:
        ``{"ok": True}`` on success.

    Raises:
        HTTPException: 422 if the body isn't a flat object of managed env names
            to string values, or if any value contains a newline (which would
            inject extra `.env` lines).
    """
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="Body must be a JSON object")

    updates: dict[str, str] = {}
    for key, value in data.items():
        if not isinstance(key, str) or not ENV_KEY_RE.match(key):
            raise HTTPException(status_code=422, detail=f"Invalid env var name: {key!r}")
        if key not in MANAGED_ENV_KEYS:
            raise HTTPException(status_code=422, detail=f"{key!r} is not settable over HTTP")
        if not isinstance(value, str):
            raise HTTPException(status_code=422, detail=f"Value for {key!r} must be a string")
        if "\n" in value or "\r" in value:
            raise HTTPException(status_code=422, detail=f"Value for {key!r} contains a newline")
        updates[key] = value

    existing = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    lines: list[str] = []
    seen: set[str] = set()

    for line in existing:
        pair = _parse_env_line(line)
        if pair is None or pair[0] not in updates:
            lines.append(line)
            continue
        key = pair[0]
        seen.add(key)
        if updates[key]:
            lines.append(f"{key}={updates[key]}")

    lines.extend(f"{k}={v}" for k, v in updates.items() if k not in seen and v)

    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"ok": True}

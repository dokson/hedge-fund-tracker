"""
Filesystem roots and path-safety helpers shared by the HTTP layer.

Both `server.py` (SPA/static serving) and the data router need to resolve
user-supplied paths inside fixed roots without path traversal, so the roots and
the basename-based sanitiser live here rather than in any single router.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException

_APP_DIR = Path(__file__).resolve().parent.parent  # .../app
_REPO_ROOT = _APP_DIR.parent  # repository root

DATABASE_DIR = _REPO_ROOT / "database"
FRONTEND_DIST = _APP_DIR / "frontend" / "dist"
ENV_FILE = _REPO_ROOT / ".env"

_DB_ROOT = DATABASE_DIR.resolve()
_FRONTEND_ROOT = FRONTEND_DIST.resolve()


def _sanitize_path_parts(filepath: str) -> list[str]:
    """Split a path into components and validate each with os.path.basename().

    os.path.basename() is the CodeQL-recognised sanitizer for py/path-injection:
    if basename(part) != part, the part contained a directory separator and is
    rejected. All parts are then used to reconstruct the path from a safe root,
    so no user-controlled string ever appears directly in a joinpath() call.

    Args:
        filepath: The untrusted, slash-or-backslash separated path.

    Returns:
        The validated, separator-free path components.

    Raises:
        ValueError: If the path is empty or any component is unsafe.
    """
    if not filepath:
        raise ValueError("Empty path")
    parts = Path(filepath).parts
    safe: list[str] = []
    for part in parts:
        clean = Path(part).name
        # Reject if basename changed (contained separator) or is a traversal token
        if not clean or clean in (".", "..") or clean != part:
            raise ValueError(f"Unsafe path component: {part!r}")
        # Reject drive letters, colons, and null bytes
        if ":" in clean or "\x00" in clean:
            raise ValueError(f"Unsafe path component: {part!r}")
        safe.append(clean)
    return safe


def _safe_db_path(filepath: str) -> Path:
    """Resolve a path inside DATABASE_DIR, rejecting traversal with HTTP 400.

    Each component is validated via os.path.basename() before being joined to
    the database root, breaking the taint chain CodeQL (py/path-injection)
    tracks from the HTTP parameter.

    Args:
        filepath: The untrusted relative path from the request.

    Returns:
        The resolved absolute path, guaranteed inside DATABASE_DIR.

    Raises:
        HTTPException: 400 if the path has unsafe characters or escapes the root.
    """
    try:
        parts = _sanitize_path_parts(filepath)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid path characters") from exc

    # Reconstruct entirely from the safe root + validated parts (no raw user input)
    resolved = _DB_ROOT.joinpath(*parts).resolve()

    # Belt-and-suspenders boundary check
    if not resolved.is_relative_to(_DB_ROOT):
        raise HTTPException(status_code=400, detail="Invalid file path")

    return resolved


def _safe_frontend_path(filepath: str) -> Path:
    """Resolve a path inside FRONTEND_DIST, rejecting traversal with HTTP 403.

    Same basename()-based sanitisation as _safe_db_path.

    Args:
        filepath: The untrusted relative path from the request.

    Returns:
        The resolved absolute path, guaranteed inside FRONTEND_DIST.

    Raises:
        HTTPException: 403 if the path has unsafe characters or escapes the root.
    """
    try:
        parts = _sanitize_path_parts(filepath)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Forbidden") from exc

    resolved = _FRONTEND_ROOT.joinpath(*parts).resolve()

    if not resolved.is_relative_to(_FRONTEND_ROOT):
        raise HTTPException(status_code=403, detail="Forbidden")

    return resolved

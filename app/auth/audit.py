"""
Helper for writing AuditLog entries safely.

Goals:
- Single chokepoint where audit events get written → grep-able / lintable.
- A denylist of metadata keys that are likely to contain secrets (`password`,
  `token`, `key`, `secret`, ...). Any matching key is dropped + logged as a
  warning, so an accidental `audit("...", token=token)` never persists the
  token in the JSONB column.

Usage:

    from app.auth.audit import audit
    audit(session, "auth.login.success", user=user, ip=request.client.host)

The session is committed by the caller; this helper only adds the row.
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog, User

logger = logging.getLogger(__name__)

# Metadata keys whose presence is almost certainly a coding mistake.
# Lookarounds use `[a-zA-Z0-9]` (NOT `\w`) so underscore is treated as a
# delimiter — that catches `user_token`, `auth_secret`, `api_key`, while
# innocent keys like `tokenizer` (token followed by 'i') and `last4` survive.
_FORBIDDEN_KEY_PATTERN = re.compile(
    r"(?<![a-zA-Z0-9])(password|passwd|pwd|secret|token|api_?key|encrypted|plaintext|dek|kek)(?![a-zA-Z0-9])",
    re.IGNORECASE,
)


def _scrub_metadata(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    """
    Drop entries whose key matches the secrets-pattern. Logs a warning so the
    accidental write surfaces in observability instead of silently passing.
    """
    if not metadata:
        return None
    cleaned: dict[str, Any] = {}
    dropped: list[str] = []
    for k, v in metadata.items():
        if _FORBIDDEN_KEY_PATTERN.search(k):
            dropped.append(k)
            continue
        cleaned[k] = v
    if dropped:
        logger.warning(
            "audit(): dropped suspicious metadata keys %r — review the call site",
            dropped,
        )
    return cleaned or None


def audit(
    session: AsyncSession,
    action: str,
    *,
    user: User | None = None,
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    """
    Add an AuditLog row. Returns the (transient) ORM instance; the caller
    decides whether to flush/commit (typically the surrounding request handler).
    """
    row = AuditLog(
        user_id=user.id if user is not None else None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip=ip,
        user_agent=user_agent,
        metadata_=_scrub_metadata(metadata),
    )
    session.add(row)
    return row

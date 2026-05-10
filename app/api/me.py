"""
Per-user endpoints under /api/me.

GDPR-relevant:
- GET  /api/me/export   — JSON dump of everything we know about the user
- DELETE /api/me/account — soft delete + 30-day hard delete schedule

Both require an active, verified user.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import delete, select

from app.auth.dependencies import current_active_verified_user
from app.db.models import AccessToken, AuditLog, User, UserSecret
from app.db.session import AsyncSessionLocal

if TYPE_CHECKING:
    pass

router = APIRouter(prefix="/api/me", tags=["me"])


def _serialize_user(user: User) -> dict:
    """
    Public, JSON-safe view of a user. Excludes hashed_password.
    """
    return {
        "id": str(user.id),
        "email": user.email,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "is_superuser": user.is_superuser,
        "tier": user.tier.value,
        "tier_expires_at": user.tier_expires_at.isoformat() if user.tier_expires_at else None,
        "display_name": user.display_name,
        "locale": user.locale,
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat(),
        "deleted_at": user.deleted_at.isoformat() if user.deleted_at else None,
    }


@router.get("/export", summary="GDPR: download all your data as JSON")
async def export_my_data(user: User = Depends(current_active_verified_user)) -> JSONResponse:
    """
    GDPR Art. 15 (right of access). Returns every row we have referencing
    this user. API keys are masked (only `last4`); secrets/ciphertext are
    omitted entirely. Future tables (api_keys, starred_items, ...) extend
    this dict.
    """
    async with AsyncSessionLocal() as session:
        audit_rows = (
            (await session.execute(select(AuditLog).where(AuditLog.user_id == user.id)))
            .scalars()
            .all()
        )

    payload = {
        "exported_at": datetime.now(UTC).isoformat(),
        "user": _serialize_user(user),
        "api_keys": [],  # populated in Phase 2
        "starred_items": [],  # populated in Phase 3
        "audit_log": [
            {
                "id": str(row.id),
                "action": row.action,
                "resource_type": row.resource_type,
                "resource_id": str(row.resource_id) if row.resource_id else None,
                "ip": str(row.ip) if row.ip else None,
                "user_agent": row.user_agent,
                "metadata": row.metadata_,
                "created_at": row.created_at.isoformat(),
            }
            for row in audit_rows
        ],
    }
    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": 'attachment; filename="my-data.json"'},
    )


@router.delete(
    "/account",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="GDPR: schedule account deletion",
)
async def delete_my_account(user: User = Depends(current_active_verified_user)) -> None:
    """
    GDPR Art. 17 (right to erasure). Soft-deletes the user account and
    revokes all sessions immediately. A scheduled cron (TODO) hard-deletes
    accounts whose `deleted_at` is older than 30 days.

    The 30-day grace lets the user reverse the decision via support; we
    don't ship a self-service "restore" UI.
    """
    async with AsyncSessionLocal() as session:
        # Mark soft-deleted and disabled.
        db_user = await session.get(User, user.id)
        if db_user is None:
            return  # already gone — idempotent
        db_user.deleted_at = datetime.now(UTC)
        db_user.is_active = False

        # Revoke all sessions (logs the user out everywhere).
        await session.execute(delete(AccessToken).where(AccessToken.user_id == user.id))

        # Drop the encryption key — even an attacker with later DB access
        # can no longer decrypt the (already stub-empty) api_keys.
        await session.execute(delete(UserSecret).where(UserSecret.user_id == user.id))

        # Audit (anonymized: user_id will be SET NULL by hard-delete cron later).
        session.add(
            AuditLog(
                user_id=user.id,
                action="account.delete_requested",
                resource_type="user",
                resource_id=user.id,
            )
        )

        await session.commit()

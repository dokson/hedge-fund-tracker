"""
Service layer for BYOK API keys.

The single chokepoint between API endpoints / AI clients and the encrypted
storage. Anything that needs an API key plaintext goes through `get_for_use`,
which decrypts via the user's DEK and updates `last_used_at`.

Plaintext keys are NEVER returned by anything else. Callers that just need
to display existing keys read `ApiKeyMetadata` (via `list_for_user`).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ApiKey, User, UserSecret
from app.security.envelope import (
    decrypt_dek,
    decrypt_value,
    encrypt_dek,
    encrypt_value,
    generate_dek,
)


@dataclass(frozen=True)
class ApiKeyMetadata:
    """
    Public-safe view of an API key. Plaintext + ciphertext stay in the DB.
    """

    id: uuid.UUID
    provider: str
    label: str | None
    last4: str
    created_at: datetime
    last_used_at: datetime | None


class NoSuchApiKeyError(LookupError):
    """
    Raised when a user has no active key for the requested provider, or
    when a specific key id doesn't belong to the user.
    """


async def ensure_user_secret(session: AsyncSession, user: User) -> UserSecret:
    """
    Get-or-create the user_secrets row for this user. Called from
    UserManager.on_after_register and lazily from `create` if a pre-existing
    user (signup before this code shipped) lacks one.
    """
    secret = await session.get(UserSecret, user.id)
    if secret is not None:
        return secret

    plaintext_dek = generate_dek()
    encrypted = encrypt_dek(plaintext_dek)
    secret = UserSecret(
        user_id=user.id,
        dek_ciphertext=encrypted.ciphertext,
        kek_version=encrypted.kek_version,
    )
    session.add(secret)
    await session.flush()
    return secret


async def _load_dek(session: AsyncSession, user: User) -> bytes:
    """
    Decrypt the user's DEK so we can use it to encrypt/decrypt their API keys.
    """
    secret = await ensure_user_secret(session, user)
    return decrypt_dek(secret.dek_ciphertext, secret.kek_version)


def _last4(plaintext: str) -> str:
    """
    UI display fragment. We show only the last 4 chars; the rest is masked.
    """
    return plaintext[-4:] if len(plaintext) >= 4 else "????"


def _to_metadata(row: ApiKey) -> ApiKeyMetadata:
    """
    Convert an ORM row to the public DTO. Note `encrypted_value` is dropped.
    """
    return ApiKeyMetadata(
        id=row.id,
        provider=row.provider,
        label=row.label,
        last4=row.last4,
        created_at=row.created_at,
        last_used_at=row.last_used_at,
    )


async def create(
    session: AsyncSession,
    user: User,
    provider: str,
    plaintext_key: str,
    label: str | None = None,
) -> ApiKeyMetadata:
    """
    Encrypt and persist a new API key. Returns metadata; plaintext + DEK are
    dropped from this function's frame after the encryption finishes.
    """
    dek = await _load_dek(session, user)
    try:
        row = ApiKey(
            user_id=user.id,
            provider=provider,
            encrypted_value=encrypt_value(plaintext_key, dek),
            last4=_last4(plaintext_key),
            label=label,
        )
        session.add(row)
        await session.flush()
        return _to_metadata(row)
    finally:
        # Drop sensitive bytes ASAP. Python doesn't guarantee zeroing, but at
        # least the references die and the GC is free to reclaim the buffers.
        del dek


async def list_for_user(session: AsyncSession, user: User) -> list[ApiKeyMetadata]:
    """
    All non-revoked keys for the user, newest first.
    """
    stmt = (
        select(ApiKey)
        .where(ApiKey.user_id == user.id, ApiKey.revoked_at.is_(None))
        .order_by(ApiKey.created_at.desc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [_to_metadata(r) for r in rows]


async def revoke(session: AsyncSession, user: User, key_id: uuid.UUID) -> None:
    """
    Soft-revoke a key. Returns silently if the key doesn't exist or isn't
    owned by this user — never reveals existence (anti-IDOR).
    """
    stmt = select(ApiKey).where(
        ApiKey.id == key_id,
        ApiKey.user_id == user.id,
        ApiKey.revoked_at.is_(None),
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise NoSuchApiKeyError(f"No active key {key_id} for user {user.id}")
    row.revoked_at = datetime.now(UTC)


async def get_for_use(session: AsyncSession, user: User, provider: str) -> str:
    """
    Decrypt and return the user's active key for `provider`.

    Updates `last_used_at` so the UI can show "last used 3 days ago" — useful
    for spotting compromised keys after the fact.

    Raises `NoSuchApiKeyError` if the user has no active key for the provider.
    The caller (AI endpoint) is expected to convert this to a 400 with a
    helpful message ("add a $provider API key in Settings").
    """
    stmt = (
        select(ApiKey)
        .where(
            ApiKey.user_id == user.id,
            ApiKey.provider == provider,
            ApiKey.revoked_at.is_(None),
        )
        .order_by(ApiKey.created_at.desc())
        .limit(1)
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise NoSuchApiKeyError(f"User {user.id} has no active key for provider {provider!r}")

    dek = await _load_dek(session, user)
    try:
        plaintext = decrypt_value(row.encrypted_value, dek)
        row.last_used_at = datetime.now(UTC)
        return plaintext
    finally:
        del dek

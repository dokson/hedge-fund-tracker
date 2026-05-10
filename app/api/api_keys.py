"""
Per-user API key endpoints under /api/me/api-keys.

All endpoints require an active, verified user. List/revoke never expose
plaintext; create accepts plaintext (over HTTPS) and returns only metadata.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Final

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, SecretStr

from app.auth import api_keys as svc
from app.auth.dependencies import current_active_verified_user
from app.db.models import User
from app.db.session import AsyncSessionLocal

router = APIRouter(prefix="/api/me/api-keys", tags=["me", "byok"])

# Providers we actually support. Must mirror the keys of `client_map` in
# app/server.py:_build_ai_client — accepting a key for a provider we don't
# wire would leave the user with a useless row + confusing 400 at AI time.
SUPPORTED_PROVIDERS: Final = {
    "github",
    "google",
    "groq",
    "huggingface",
    "openrouter",
}


class CreateApiKeyPayload(BaseModel):
    """
    Signup-time payload. `plaintext` is `SecretStr` so its value is never
    stringified into logs or repr (Pydantic's default repr shows '**********').
    The encrypted bytes are persisted; the plaintext is dropped before the
    response is built.
    """

    provider: str = Field(..., description="Provider identifier (e.g. 'openai')")
    plaintext: SecretStr = Field(..., min_length=8, max_length=512, description="The raw API key")
    label: str | None = Field(default=None, max_length=80)


class ApiKeyMetadataOut(BaseModel):
    """
    Wire format for ApiKeyMetadata. Pydantic validates plaintext can never
    accidentally be added to the response (no encrypted_value field).
    """

    id: uuid.UUID
    provider: str
    label: str | None
    last4: str
    created_at: datetime
    last_used_at: datetime | None


def _to_out(meta: svc.ApiKeyMetadata) -> ApiKeyMetadataOut:
    """
    Map service DTO to wire DTO.
    """
    return ApiKeyMetadataOut(
        id=meta.id,
        provider=meta.provider,
        label=meta.label,
        last4=meta.last4,
        created_at=meta.created_at,
        last_used_at=meta.last_used_at,
    )


@router.get("", response_model=list[ApiKeyMetadataOut])
async def list_api_keys(
    user: User = Depends(current_active_verified_user),
) -> list[ApiKeyMetadataOut]:
    """
    List the user's active (non-revoked) API keys. Metadata only.
    """
    async with AsyncSessionLocal() as session:
        return [_to_out(m) for m in await svc.list_for_user(session, user)]


@router.post(
    "",
    response_model=ApiKeyMetadataOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_api_key(
    payload: CreateApiKeyPayload,
    user: User = Depends(current_active_verified_user),
) -> ApiKeyMetadataOut:
    """
    Add a new API key. Provider must be one of SUPPORTED_PROVIDERS.
    """
    if payload.provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider {payload.provider!r}. "
            f"Allowed: {sorted(SUPPORTED_PROVIDERS)}",
        )

    async with AsyncSessionLocal() as session:
        # Unwrap the SecretStr only here, at the encryption boundary. The local
        # `plaintext_key` variable goes out of scope on function return; we
        # don't store it in self/state anywhere.
        plaintext_key = payload.plaintext.get_secret_value()
        try:
            meta = await svc.create(
                session=session,
                user=user,
                provider=payload.provider,
                plaintext_key=plaintext_key,
                label=payload.label,
            )
            await session.commit()
            return _to_out(meta)
        finally:
            # Best-effort scrub of the plaintext from this frame before GC.
            # Python doesn't guarantee memory zeroing, but `del` makes the GC
            # eligible immediately and prevents accidental reuse.
            del plaintext_key


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: uuid.UUID,
    user: User = Depends(current_active_verified_user),
) -> None:
    """
    Soft-revoke a key. Returns 204 if revoked; 404 if the key doesn't exist
    or doesn't belong to the user (we don't differentiate, anti-IDOR).
    """
    async with AsyncSessionLocal() as session:
        try:
            await svc.revoke(session, user, key_id)
        except svc.NoSuchApiKeyError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
        await session.commit()

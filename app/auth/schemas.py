"""
Pydantic schemas for the auth API surface.

These define what the client sees / sends. Keep them minimal — anything
sensitive (hashed_password, dek_ciphertext, ...) MUST stay out of UserRead.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi_users import schemas
from pydantic import ConfigDict, Field

from app.db.models import UserTier


class UserRead(schemas.BaseUser[uuid.UUID]):
    """
    What we send back to the client. Inherits the safe fastapi-users fields:
    id, email, is_active, is_verified, is_superuser. Adds our extensions.
    """

    tier: UserTier
    display_name: str | None = None
    locale: str = "en"
    created_at: datetime


class UserCreate(schemas.BaseUserCreate):
    """
    Signup payload. fastapi-users gives us email + password; we add the
    optional bits new users can self-set.
    """

    display_name: str | None = Field(default=None, max_length=80)
    locale: str = Field(default="en", min_length=2, max_length=8)


class UserUpdate(schemas.BaseUserUpdate):
    """
    Profile-update payload. We deliberately do NOT expose `tier` or
    `is_superuser` here — those are server-side only (Stripe webhook / admin).

    `extra="forbid"` makes the API reject unknown fields with a 422 instead of
    silently dropping them. Without this, a future Pydantic regression that
    auto-applies extra fields could become a privilege-escalation bug.
    """

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, max_length=80)
    locale: str | None = Field(default=None, min_length=2, max_length=8)

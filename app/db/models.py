"""
SQLAlchemy ORM models.

Every new model file MUST be imported here (or by a chain rooted here) so that
`Base.metadata` is populated for Alembic autogenerate / migration env.

Convention:
- Public IDs are UUID v7 (sortable + non-enumerable). Postgres 16 doesn't ship
  uuidv7() natively yet, so the migration creates a SQL function for it.
- All timestamps are timestamptz (UTC at the DB layer; convert at the edge).
- Soft-delete columns (`deleted_at`) are nullable timestamptz; queries must
  filter `WHERE deleted_at IS NULL` unless explicitly looking at the trash.

`User` and `AccessToken` extend the fastapi-users SQLAlchemy mixins so the
auth library works out of the box; we override the columns that need
PostgreSQL-specific types (CITEXT email, uuidv7() default) so `alembic check`
agrees with the actual schema.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from fastapi_users.db import SQLAlchemyBaseUserTableUUID  # pyright: ignore[reportMissingImports]
from fastapi_users_db_sqlalchemy.access_token import (  # pyright: ignore[reportMissingImports]
    SQLAlchemyBaseAccessTokenTableUUID,
)
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import CITEXT, INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class UserTier(enum.StrEnum):
    """
    Subscription tiers. Stored as a Postgres enum named `user_tier`.
    """

    FREE = "free"
    PRO = "pro"
    TEAM = "team"


class StarredItemType(enum.StrEnum):
    """
    What the user can star. Stored as a Postgres enum named `starred_item_type`.
    """

    STOCK = "stock"
    FUND = "fund"
    QUARTER = "quarter"


class User(SQLAlchemyBaseUserTableUUID, Base):
    """
    Authenticated user. Owns api keys, starred items, and (later) portfolios.

    Inherits from `SQLAlchemyBaseUserTableUUID` for compatibility with
    fastapi-users, but overrides `id`, `email`, `hashed_password` and the
    boolean defaults to match our Postgres schema (uuidv7, citext, ...).
    """

    __tablename__ = "users"

    # Override the id default so alembic check sees uuidv7() at the DB layer.
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuidv7()"),
    )
    email: Mapped[str] = mapped_column(CITEXT(), nullable=False)
    hashed_password: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_superuser: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    tier: Mapped[UserTier] = mapped_column(
        SAEnum(UserTier, name="user_tier", values_callable=lambda e: [v.value for v in e]),
        nullable=False,
        server_default=text("'free'"),
    )
    tier_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    display_name: Mapped[str | None] = mapped_column(Text)
    locale: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'en'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    secret: Mapped[UserSecret | None] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("email", name="users_email_unique"),
        # Partial index: cheap "list active users by tier" lookups.
        Index(
            "users_tier_active",
            "tier",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover
        """
        Compact, no-PII repr for debug logs.
        """
        return f"<User id={self.id} tier={self.tier.value}>"


class AccessToken(SQLAlchemyBaseAccessTokenTableUUID, Base):
    """
    Server-side session tokens for cookie-based auth (revocable).

    Overrides:
    - user_id FK → 'users.id' (mixin default points at 'user.id', singular).
    - created_at server_default → now() so the schema agrees with the migration.
    """

    __tablename__ = "accesstoken"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        Index("accesstoken_user_id", "user_id"),
        Index("accesstoken_created_at", text("created_at DESC")),
    )


class UserSecret(Base):
    """
    Per-user data encryption key (DEK), itself encrypted with the master KEK.

    Kept in a separate table so the hot-path `users` row stays small and
    cacheable; the DEK is loaded only when the user makes an AI call that
    needs to decrypt their api key.
    """

    __tablename__ = "user_secrets"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    dek_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    kek_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    rotated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="secret")


class ApiKey(Base):
    """
    BYOK API key for an external AI provider (openai, anthropic, groq, ...).

    Storage rules (enforced at the service layer):
    - `encrypted_value` is the user's plaintext key encrypted with their DEK.
    - `last4` is the only display surface (UI shows `sk-...QXY7`).
    - Plaintext is NEVER returned by any endpoint. The /api/me/api-keys list
      returns metadata only. To "see" a key, the user re-pastes it.
    - `revoked_at` is soft-revocation; cron hard-deletes after 90 days.
    """

    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuidv7()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_value: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    last4: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "api_keys_user_active",
            "user_id",
            "provider",
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )


class StarredItem(Base):
    """
    A user's saved favorite. Replaces the legacy localStorage star state.

    `item_id` is free-form text (no FK) because the targets live in CSV files
    we don't relationally model: ticker for stock, fund denomination for fund,
    quarter string for quarter. Application-layer regex validates per type.
    """

    __tablename__ = "starred_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuidv7()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    item_type: Mapped[StarredItemType] = mapped_column(
        SAEnum(
            StarredItemType,
            name="starred_item_type",
            values_callable=lambda e: [v.value for v in e],
        ),
        nullable=False,
    )
    item_id: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    starred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("user_id", "item_type", "item_id", name="starred_items_unique"),
        Index("starred_items_user_type", "user_id", "item_type"),
    )


class AuditLog(Base):
    """
    Append-only security event log. `user_id` is nullable + ON DELETE SET NULL
    so the trail survives account deletion (anonymized).

    `action` is a free-form dotted string ('auth.login.success',
    'api_key.create', 'account.delete_executed', ...). Avoid putting secrets
    in `metadata` — it's queryable JSON.
    """

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuidv7()"),
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    resource_type: Mapped[str | None] = mapped_column(Text)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    ip: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("audit_log_user_time", "user_id", text("created_at DESC")),)

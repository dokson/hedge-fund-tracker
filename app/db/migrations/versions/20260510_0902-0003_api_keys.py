"""api_keys table for BYOK

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-10 09:02:00

Stores users' encrypted external API keys (OpenAI, Anthropic, Groq, ...).
The encryption layer is in app/security/envelope.py — this migration only
sets up the storage shape.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Apply the migration. The partial index on (user_id, provider) WHERE
    revoked_at IS NULL makes "find this user's active key for provider X"
    a single index hit.
    """
    op.create_table(
        "api_keys",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuidv7()"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("encrypted_value", sa.LargeBinary(), nullable=False),
        sa.Column("last4", sa.Text(), nullable=False),
        sa.Column("label", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.execute(
        "CREATE INDEX api_keys_user_active ON api_keys (user_id, provider) WHERE revoked_at IS NULL"
    )


def downgrade() -> None:
    """
    Reverse the migration.
    """
    op.drop_index("api_keys_user_active", table_name="api_keys")
    op.drop_table("api_keys")

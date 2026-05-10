"""accesstoken table for fastapi-users DatabaseStrategy

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-10 09:01:00

Adds the server-side session token table. Each row is one valid session;
deleting a row revokes that session. Required by fastapi-users when using
DatabaseStrategy (vs JWT) — chosen so we can implement "sign out all devices".
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Apply the migration. Token is a 43-char URL-safe random string (the
    fastapi-users default); we store as Text since the column has no length
    bound that's worth enforcing at the DB layer.
    """
    op.create_table(
        "accesstoken",
        sa.Column("token", sa.String(length=43), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("accesstoken_user_id", "accesstoken", ["user_id"])
    op.create_index(
        "accesstoken_created_at",
        "accesstoken",
        [sa.text("created_at DESC")],
    )


def downgrade() -> None:
    """
    Reverse the migration.
    """
    op.drop_index("accesstoken_created_at", table_name="accesstoken")
    op.drop_index("accesstoken_user_id", table_name="accesstoken")
    op.drop_table("accesstoken")

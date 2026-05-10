"""starred_items table

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-10 09:03:00

Server-backed favorites. Replaces the localStorage-only state from the
`useStarred` frontend hook. Each row is one starred entity (stock / fund /
quarter); UNIQUE(user_id, item_type, item_id) prevents duplicates.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Apply the migration. Creates the enum + table + supporting index.
    """
    starred_item_type = postgresql.ENUM(
        "stock", "fund", "quarter", name="starred_item_type", create_type=False
    )
    starred_item_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "starred_items",
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
        sa.Column("item_type", starred_item_type, nullable=False),
        sa.Column("item_id", sa.Text(), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column(
            "starred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("user_id", "item_type", "item_id", name="starred_items_unique"),
    )
    op.create_index("starred_items_user_type", "starred_items", ["user_id", "item_type"])


def downgrade() -> None:
    """
    Reverse the migration.
    """
    op.drop_index("starred_items_user_type", table_name="starred_items")
    op.drop_table("starred_items")
    op.execute("DROP TYPE IF EXISTS starred_item_type")

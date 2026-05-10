"""users + user_secrets + audit_log

Revision ID: 0001
Revises:
Create Date: 2026-05-10 09:00:00

This is the first real migration. It bootstraps:
- Postgres extensions: citext (case-insensitive email), pgcrypto (random bytes).
- A SQL function uuidv7() so all primary keys are time-sortable + non-enumerable.
- A reusable trigger to keep `updated_at` honest on UPDATE.
- The `user_tier` enum.
- Tables: users, user_secrets, audit_log with their indexes.

Down-migration drops everything in reverse, including the function and trigger.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Alembic identifiers.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


# -- uuidv7() --------------------------------------------------------------
# Postgres 16 doesn't ship uuidv7() (lands in PG18). This SQL function is the
# Buildkite/Supabase-style implementation: 48-bit Unix ms timestamp + 74 random
# bits, formatted per RFC 9562. Time-sortable, monotonic enough for inserts.
UUIDV7_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION uuidv7() RETURNS uuid AS $$
DECLARE
    unix_ts_ms bytea;
    rand_bytes bytea;
    uuid_bytes bytea;
BEGIN
    unix_ts_ms := substring(int8send((extract(epoch FROM clock_timestamp()) * 1000)::bigint) FROM 3);
    rand_bytes := gen_random_bytes(10);
    uuid_bytes := unix_ts_ms || rand_bytes;
    -- Set version (7) in the upper nibble of byte 7
    uuid_bytes := set_byte(uuid_bytes, 6, (b'01110000'::bit(8) | (get_byte(uuid_bytes, 6)::bit(8) & b'00001111'))::int);
    -- Set variant (RFC 4122) in the upper bits of byte 9
    uuid_bytes := set_byte(uuid_bytes, 8, (b'10000000'::bit(8) | (get_byte(uuid_bytes, 8)::bit(8) & b'00111111'))::int);
    RETURN encode(uuid_bytes, 'hex')::uuid;
END;
$$ LANGUAGE plpgsql VOLATILE;
"""

UPDATED_AT_TRIGGER_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    """
    Apply the migration. Idempotent on extensions (CREATE EXTENSION IF NOT EXISTS),
    not idempotent on tables (Alembic version table tracks state).
    """
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")  # for gen_random_bytes
    op.execute(UUIDV7_FUNCTION_SQL)
    op.execute(UPDATED_AT_TRIGGER_FUNCTION_SQL)

    user_tier = postgresql.ENUM("free", "pro", "team", name="user_tier", create_type=False)
    user_tier.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuidv7()"),
            primary_key=True,
        ),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("hashed_password", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("tier", user_tier, nullable=False, server_default=sa.text("'free'")),
        sa.Column("tier_expires_at", sa.DateTime(timezone=True)),
        sa.Column("display_name", sa.Text()),
        sa.Column("locale", sa.Text(), nullable=False, server_default=sa.text("'en'")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("email", name="users_email_unique"),
    )
    op.execute("CREATE INDEX users_tier_active ON users (tier) WHERE deleted_at IS NULL")
    op.execute(
        "CREATE TRIGGER users_set_updated_at BEFORE UPDATE ON users "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )

    op.create_table(
        "user_secrets",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("dek_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("kek_version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "rotated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "audit_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuidv7()"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("resource_type", sa.Text()),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True)),
        sa.Column("ip", postgresql.INET()),
        sa.Column("user_agent", sa.Text()),
        sa.Column("metadata", postgresql.JSONB()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("audit_log_user_time", "audit_log", ["user_id", sa.text("created_at DESC")])


def downgrade() -> None:
    """
    Reverse the migration. Drops in dependency order (audit_log first because
    it FKs users), then the trigger, function, enum, extensions intentionally
    NOT dropped (other databases on the same instance might use them).
    """
    op.drop_index("audit_log_user_time", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_table("user_secrets")
    op.execute("DROP TRIGGER IF EXISTS users_set_updated_at ON users")
    op.drop_index("users_tier_active", table_name="users")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS user_tier")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")
    op.execute("DROP FUNCTION IF EXISTS uuidv7()")

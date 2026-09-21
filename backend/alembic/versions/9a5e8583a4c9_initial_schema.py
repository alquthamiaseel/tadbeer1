"""initial schema: users only

The database is authentication only — pipeline state (runs, stages, artifacts,
captured Slack messages, the audit log) is runtime memory now, not persisted.
This migration replaces the original one, which created those five tables; if
you are upgrading an existing database, drop it and re-run `make migrate`
rather than trying to migrate the old data forward, since none of it is kept
by the app anymore.

Revision ID: 9a5e8583a4c9
Revises:
Create Date: 2026-08-14 02:50:19.095617
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "9a5e8583a4c9"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_table("users")

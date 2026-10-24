"""Feature 003 (US6): schedules gain their own target + optional label,
and a profile may now have more than one schedule.

`profile_id` was previously enforced unique via the single named index
`ix_schedules_profile_id` (SQLite reflection confirms no separate inline
UNIQUE constraint is involved — the only other autoindex on this table
backs the primary key). Dropping that index and recreating it without
`unique=True` is therefore sufficient; no table rebuild is required.

Revision ID: 0003_schedule_target_and_label
Revises: 0002_feature_002
Create Date: 2026-10-22

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_schedule_target_and_label"
down_revision: str | None = "0002_feature_002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {c["name"] for c in inspector.get_columns("schedules")}

    if "target_scope" not in existing_columns:
        op.add_column(
            "schedules",
            sa.Column("target_scope", sa.JSON(), nullable=False, server_default="[]"),
        )

    if "label" not in existing_columns:
        op.add_column("schedules", sa.Column("label", sa.String(length=128), nullable=True))

    existing_indexes = {ix["name"] for ix in inspector.get_indexes("schedules")}
    if "ix_schedules_profile_id" in existing_indexes:
        op.drop_index("ix_schedules_profile_id", table_name="schedules")
    op.create_index("ix_schedules_profile_id", "schedules", ["profile_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_schedules_profile_id", table_name="schedules")
    op.create_index("ix_schedules_profile_id", "schedules", ["profile_id"], unique=True)

    with op.batch_alter_table("schedules") as batch_op:
        batch_op.drop_column("label")
        batch_op.drop_column("target_scope")

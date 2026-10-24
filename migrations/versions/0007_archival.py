"""Row-count-based archival for the ever-growing history-style tables
(discovery_runs, schedules, tool_check_runs): adds an `archived` flag to
each (default false), plus `created_at` on `schedules` (needed as the
"oldest first" ordering basis for archival — Schedule previously had no
creation timestamp). See archival.py.

Revision ID: 0007_archival
Revises: 0006_legacy_columns_nullable
Create Date: 2026-10-23

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_archival"
down_revision: str | None = "0006_legacy_columns_nullable"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES_WITH_ARCHIVED = ("discovery_runs", "schedules", "tool_check_runs")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table in _TABLES_WITH_ARCHIVED:
        existing_columns = {c["name"] for c in inspector.get_columns(table)}
        if "archived" not in existing_columns:
            with op.batch_alter_table(table) as batch_op:
                batch_op.add_column(
                    sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false())
                )
        existing_indexes = {ix["name"] for ix in inspector.get_indexes(table)}
        index_name = f"ix_{table}_archived"
        if index_name not in existing_indexes:
            op.create_index(index_name, table, ["archived"])

    schedules_columns = {c["name"] for c in inspector.get_columns("schedules")}
    if "created_at" not in schedules_columns:
        with op.batch_alter_table("schedules") as batch_op:
            # No historical creation time exists for pre-existing rows;
            # default them to "now" (upgrade time) rather than guessing —
            # only affects relative archival order among schedules that
            # already existed before this migration ran.
            batch_op.add_column(
                sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now())
            )
        existing_indexes = {ix["name"] for ix in inspector.get_indexes("schedules")}
        if "ix_schedules_created_at" not in existing_indexes:
            op.create_index("ix_schedules_created_at", "schedules", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_schedules_created_at", table_name="schedules")
    with op.batch_alter_table("schedules") as batch_op:
        batch_op.drop_column("created_at")

    for table in _TABLES_WITH_ARCHIVED:
        op.drop_index(f"ix_{table}_archived", table_name=table)
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_column("archived")

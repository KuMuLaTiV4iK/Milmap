"""Fix: `reference_version_entries.version_match`/`status` are retained as
legacy migration provenance (data-model.md §1, "RETAIN (legacy)") and the
ORM model has declared them `Optional` since the V0.7 overhaul — but no
prior migration ever relaxed their original `NOT NULL` constraint on an
upgraded (non-fresh-install) database. New manual/ingested threshold rows
never populate them, so the NOT NULL constraint blocked every create
(`sqlite3.IntegrityError: NOT NULL constraint failed: ...version_match`).

Revision ID: 0006_legacy_columns_nullable
Revises: 0005_device_type
Create Date: 2026-10-23

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_legacy_columns_nullable"
down_revision: str | None = "0005_device_type"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("reference_version_entries") as batch_op:
        batch_op.alter_column(
            "version_match", existing_type=sa.String(length=128), nullable=True
        )
        batch_op.alter_column("status", existing_type=sa.String(length=16), nullable=True)


def downgrade() -> None:
    """Best-effort: restores NOT NULL. Any row written since this
    migration with a NULL `version_match`/`status` (i.e. every row created
    by the V0.7 threshold model) will fail this downgrade — a documented
    one-way change for any post-V0.7 data."""
    with op.batch_alter_table("reference_version_entries") as batch_op:
        batch_op.alter_column(
            "version_match", existing_type=sa.String(length=128), nullable=False
        )
        batch_op.alter_column("status", existing_type=sa.String(length=16), nullable=False)

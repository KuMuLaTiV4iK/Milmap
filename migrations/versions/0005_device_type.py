"""V0.7 follow-up: replace `product` (free-text) with `type` (a
constrained physical-device category: ip_phone/voip_gateway/ata/ucm/
switch/router) on `reference_version_entries`.

Compliance matching moves from substring-matching the `product` text to
matching `vendor` (+`model`) — a device-type category cannot be expected
to appear in a scanned service/firmware banner string, so it was never a
sound match key (see compliance/version_check.py). Existing rows keep
their `vendor`/`model`; `type` is left NULL for them (no `product`-derived
mapping is attempted) and surfaces as "unclassified" until an
administrator assigns one.

Revision ID: 0005_device_type
Revises: 0004_version_dictionary_overhaul
Create Date: 2026-10-23

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_device_type"
down_revision: str | None = "0004_version_dictionary_overhaul"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {c["name"] for c in inspector.get_columns("reference_version_entries")}
    existing_indexes = {ix["name"] for ix in inspector.get_indexes("reference_version_entries")}

    # Drop any index on `product` BEFORE the batch recreate below — SQLite
    # batch mode reflects and tries to recreate every existing index
    # verbatim, including one never declared by an Alembic migration (a
    # fresh install's `create_all()` auto-creates `ix_..._product` from the
    # ORM's old `index=True`), which would otherwise reference a column
    # that no longer exists once `product` is dropped in this same batch.
    if "ix_reference_version_entries_product" in existing_indexes:
        op.drop_index("ix_reference_version_entries_product", table_name="reference_version_entries")

    with op.batch_alter_table("reference_version_entries") as batch_op:
        if "type" not in existing_columns:
            batch_op.add_column(sa.Column("type", sa.String(length=32), nullable=True))
        if "product" in existing_columns:
            batch_op.drop_column("product")

    existing_indexes = {ix["name"] for ix in inspector.get_indexes("reference_version_entries")}
    if "ix_reference_version_entries_type" not in existing_indexes:
        op.create_index(
            "ix_reference_version_entries_type", "reference_version_entries", ["type"]
        )


def downgrade() -> None:
    """Best-effort: restores `product` as nullable (original text values
    are NOT reconstructed — a documented one-way transform) and drops
    `type`."""
    op.drop_index("ix_reference_version_entries_type", table_name="reference_version_entries")
    with op.batch_alter_table("reference_version_entries") as batch_op:
        batch_op.add_column(sa.Column("product", sa.String(length=128), nullable=True))
        batch_op.drop_column("type")
    op.create_index(
        "ix_reference_version_entries_product", "reference_version_entries", ["product"]
    )

"""V0.7 Version Dictionary Overhaul: enumerated -> minimum-version threshold.

Adds threshold/provenance columns to `reference_version_entries` and the new
`version_ingestion_sources` table (data-model.md §1-§2), then runs the
enumerated-to-threshold data migration (research D3): for each
(vendor, product) group, `min_version` becomes the lowest `valid` version on
record (wildcard floors like `9.*` normalize to `9.0`); the group collapses
to a single row. A group with only `invalid` rows is NOT auto-converted —
it is kept as one row with `min_version=NULL` and `needs_review=true` for
administrator review.

Revision ID: 0004_version_dictionary_overhaul
Revises: 0003_schedule_target_and_label
Create Date: 2026-10-23

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_version_dictionary_overhaul"
down_revision: str | None = "0003_schedule_target_and_label"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _lowest_valid_floor(version_matches: list[str]) -> str | None:
    """Lowest `valid` version among `version_matches`, using the app's
    comparator (research D1); wildcard floors (`9.*`) normalize to `9.0`."""
    from asset_dashboard.compliance.version_compare import (
        compare_versions,
        normalize_wildcard_floor,
    )

    floors = [normalize_wildcard_floor(v) for v in version_matches]
    lowest = None
    for floor in floors:
        if lowest is None:
            lowest = floor
            continue
        comparison = compare_versions(floor, lowest)
        if comparison is not None and comparison < 0:
            lowest = floor
    return lowest


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {c["name"] for c in inspector.get_columns("reference_version_entries")}

    with op.batch_alter_table("reference_version_entries") as batch_op:
        if "min_version" not in existing_columns:
            batch_op.add_column(sa.Column("min_version", sa.String(length=128), nullable=True))
        if "model" not in existing_columns:
            batch_op.add_column(sa.Column("model", sa.String(length=128), nullable=True))
        if "source" not in existing_columns:
            batch_op.add_column(
                sa.Column("source", sa.String(length=16), nullable=False, server_default="manual")
            )
        if "source_ref" not in existing_columns:
            batch_op.add_column(sa.Column("source_ref", sa.String(length=256), nullable=True))
        if "needs_review" not in existing_columns:
            batch_op.add_column(
                sa.Column("needs_review", sa.Boolean(), nullable=False, server_default=sa.false())
            )
        if "updated_at" not in existing_columns:
            batch_op.add_column(sa.Column("updated_at", sa.DateTime(), nullable=True))

    existing_indexes = {ix["name"] for ix in inspector.get_indexes("reference_version_entries")}
    if "ix_reference_version_entries_model" not in existing_indexes:
        op.create_index(
            "ix_reference_version_entries_model", "reference_version_entries", ["model"]
        )

    existing_tables = set(inspector.get_table_names())
    if "version_ingestion_sources" not in existing_tables:
        op.create_table(
            "version_ingestion_sources",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("vendor", sa.String(length=128), nullable=False),
            sa.Column("source_url", sa.String(length=512), nullable=False),
            sa.Column("models", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("extractor", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("last_import_status", sa.String(length=16), nullable=True),
            sa.Column("last_import_at", sa.DateTime(), nullable=True),
            sa.Column("last_versions", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column(
                "created_by",
                sa.String(length=36),
                sa.ForeignKey("operator_accounts.id"),
                nullable=True,
            ),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index(
            "ix_version_ingestion_sources_vendor", "version_ingestion_sources", ["vendor"]
        )

    _migrate_enumerated_to_threshold(bind)


def _migrate_enumerated_to_threshold(bind: sa.engine.Connection) -> tuple[int, int]:
    """Collapse each (vendor, product) group of legacy enumerated rows into
    a single threshold row. Returns (converted_count, flagged_count) for
    the upgrade log."""
    entries_table = sa.table(
        "reference_version_entries",
        sa.column("id", sa.String),
        sa.column("vendor", sa.String),
        sa.column("product", sa.String),
        sa.column("version_match", sa.String),
        sa.column("status", sa.String),
        sa.column("note", sa.Text),
        sa.column("min_version", sa.String),
        sa.column("source", sa.String),
        sa.column("needs_review", sa.Boolean),
    )

    rows = bind.execute(
        sa.select(
            entries_table.c.id,
            entries_table.c.vendor,
            entries_table.c.product,
            entries_table.c.version_match,
            entries_table.c.status,
            entries_table.c.note,
        )
    ).fetchall()

    groups: dict[tuple[str, str], list] = {}
    for row in rows:
        groups.setdefault((row.vendor, row.product), []).append(row)

    converted = 0
    flagged = 0

    for (_vendor, _product), group_rows in groups.items():
        valid_matches = [
            r.version_match for r in group_rows if r.status == "valid" and r.version_match
        ]
        keep_row = group_rows[0]
        drop_ids = [r.id for r in group_rows[1:]]

        if valid_matches:
            floor = _lowest_valid_floor(valid_matches)
            bind.execute(
                entries_table.update()
                .where(entries_table.c.id == keep_row.id)
                .values(min_version=floor, source="manual", needs_review=False)
            )
            converted += 1
        else:
            # Invalid-only group: not auto-converted, flagged for review.
            bind.execute(
                entries_table.update()
                .where(entries_table.c.id == keep_row.id)
                .values(min_version=None, source="manual", needs_review=True)
            )
            flagged += 1

        if drop_ids:
            bind.execute(entries_table.delete().where(entries_table.c.id.in_(drop_ids)))

    print(
        f"migration 0004: converted {converted} product group(s) to a threshold; "
        f"flagged {flagged} invalid-only group(s) for review."
    )
    return converted, flagged


def downgrade() -> None:
    """Best-effort: drops the threshold/provenance columns and the ingestion
    table. This is a documented ONE-WAY data transform — the original
    enumerated rows collapsed during `upgrade()` are NOT reconstructed."""
    op.drop_index("ix_version_ingestion_sources_vendor", table_name="version_ingestion_sources")
    op.drop_table("version_ingestion_sources")

    op.drop_index("ix_reference_version_entries_model", table_name="reference_version_entries")
    with op.batch_alter_table("reference_version_entries") as batch_op:
        batch_op.drop_column("updated_at")
        batch_op.drop_column("needs_review")
        batch_op.drop_column("source_ref")
        batch_op.drop_column("source")
        batch_op.drop_column("model")
        batch_op.drop_column("min_version")

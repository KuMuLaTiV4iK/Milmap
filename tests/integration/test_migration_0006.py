"""Regression test: on a database upgraded from pre-V0.7 (not a fresh
`create_all()` install), `version_match`/`status` were left `NOT NULL`
by migration 0005, which blocked every new manual/ingested threshold
create (`IntegrityError`). Migration 0006 relaxes them."""
from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from asset_dashboard.config import settings as app_settings

REPO_ROOT = Path(__file__).resolve().parents[2]


def _build_post_0005_schema_with_not_null_legacy_columns(db_url: str) -> None:
    """Mirrors what an *upgraded* (not fresh-install) database actually
    looks like after 0002->0005: `version_match`/`status` still carry
    their original NOT NULL from the feature-001 baseline, since no prior
    migration touched that constraint."""
    engine = sa.create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE operator_accounts (id VARCHAR(36) PRIMARY KEY)"))
        conn.execute(
            sa.text(
                """
                CREATE TABLE reference_version_entries (
                    id VARCHAR(36) PRIMARY KEY,
                    vendor VARCHAR(128) NOT NULL,
                    version_match VARCHAR(128) NOT NULL,
                    status VARCHAR(16) NOT NULL,
                    note TEXT,
                    min_version VARCHAR(128),
                    model VARCHAR(128),
                    source VARCHAR(16) NOT NULL DEFAULT 'manual',
                    source_ref VARCHAR(256),
                    needs_review BOOLEAN NOT NULL DEFAULT 0,
                    updated_at DATETIME,
                    type VARCHAR(32)
                )
                """
            )
        )
        conn.execute(
            sa.text(
                "CREATE TABLE version_ingestion_sources (id VARCHAR(36) PRIMARY KEY, vendor VARCHAR(128))"
            )
        )
    engine.dispose()


def test_migration_0006_allows_a_new_threshold_row_with_no_legacy_fields(tmp_path, monkeypatch):
    db_path = tmp_path / "post_0005.sqlite3"
    db_url = f"sqlite:///{db_path.as_posix()}"
    _build_post_0005_schema_with_not_null_legacy_columns(db_url)

    monkeypatch.setattr(app_settings, "database_url", db_url)

    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    command.stamp(cfg, "0005_device_type")
    command.upgrade(cfg, "0006_legacy_columns_nullable")

    engine = sa.create_engine(db_url)
    with engine.begin() as conn:
        # No version_match/status supplied — this is exactly the shape the
        # app writes for every new manual/ingested threshold row.
        conn.execute(
            sa.text(
                "INSERT INTO reference_version_entries (id, vendor, type, model, min_version, source) "
                "VALUES ('t1', 'Mikrotik', 'router', 'RB', '7.23.8', 'manual')"
            )
        )
    engine.dispose()

"""Migration 0005 (device-type follow-up): `product` is dropped,
`type` is added (nullable, unset for pre-existing rows)."""
from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from asset_dashboard.config import settings as app_settings

REPO_ROOT = Path(__file__).resolve().parents[2]


def _build_post_0004_schema(db_url: str) -> None:
    """A reference_version_entries table shaped like migration 0004's
    output (vendor/product/model/min_version/source/etc., no `type` yet),
    with one existing threshold row."""
    engine = sa.create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                """
                CREATE TABLE operator_accounts (
                    id VARCHAR(36) PRIMARY KEY
                )
                """
            )
        )
        conn.execute(
            sa.text(
                """
                CREATE TABLE reference_version_entries (
                    id VARCHAR(36) PRIMARY KEY,
                    vendor VARCHAR(128),
                    product VARCHAR(128),
                    model VARCHAR(128),
                    min_version VARCHAR(128),
                    source VARCHAR(16),
                    source_ref VARCHAR(256),
                    needs_review BOOLEAN,
                    updated_at DATETIME,
                    version_match VARCHAR(128),
                    status VARCHAR(16),
                    note TEXT
                )
                """
            )
        )
        conn.execute(
            sa.text(
                "INSERT INTO reference_version_entries "
                "(id, vendor, product, min_version, source, needs_review) VALUES "
                "('e1', 'OpenSSH', 'OpenSSH', '9.0', 'manual', 0)"
            )
        )
        conn.execute(
            sa.text(
                """
                CREATE TABLE version_ingestion_sources (
                    id VARCHAR(36) PRIMARY KEY,
                    vendor VARCHAR(128)
                )
                """
            )
        )
    engine.dispose()


def test_migration_0005_drops_product_and_adds_type(tmp_path, monkeypatch):
    db_path = tmp_path / "post_0004.sqlite3"
    db_url = f"sqlite:///{db_path.as_posix()}"
    _build_post_0004_schema(db_url)

    monkeypatch.setattr(app_settings, "database_url", db_url)

    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    command.stamp(cfg, "0004_version_dictionary_overhaul")
    command.upgrade(cfg, "0005_device_type")

    engine = sa.create_engine(db_url)
    inspector = sa.inspect(engine)
    columns = {c["name"] for c in inspector.get_columns("reference_version_entries")}
    assert "product" not in columns
    assert "type" in columns

    with engine.connect() as conn:
        row = conn.execute(
            sa.text("SELECT vendor, type, min_version FROM reference_version_entries")
        ).fetchone()
    engine.dispose()

    assert row.vendor == "OpenSSH"
    assert row.type is None  # not auto-assigned; left for an administrator to classify
    assert row.min_version == "9.0"

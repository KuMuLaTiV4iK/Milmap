"""Migration integration test (FR-012, SC-008): seed pre-V0.7 enumerated
rows, run `alembic upgrade head`, and assert the lowest-`valid` derivation,
single collapsed row per product, and `needs_review=true` on an
invalid-only product."""

from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from asset_dashboard.config import settings as app_settings

REPO_ROOT = Path(__file__).resolve().parents[2]


def _build_pre_v07_schema(db_url: str) -> None:
    """Minimal pre-V0.7 baseline (the tables 0002/0003 touch, plus the
    legacy-shaped reference_version_entries), seeded with enumerated rows:
    OpenSSH 7.* invalid / 9.* valid (collapses to min_version=9.0), and an
    invalid-only product (flagged for review, no auto floor)."""
    engine = sa.create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                """
                CREATE TABLE operator_accounts (
                    id VARCHAR(36) PRIMARY KEY,
                    username VARCHAR(64),
                    password_hash VARCHAR(256),
                    status VARCHAR(16),
                    failed_attempts INTEGER,
                    lock_until DATETIME,
                    created_at DATETIME,
                    updated_at DATETIME
                )
                """
            )
        )
        conn.execute(
            sa.text(
                """
                CREATE TABLE schedules (
                    id VARCHAR(36) PRIMARY KEY,
                    profile_id VARCHAR(36),
                    recurrence JSON,
                    enabled BOOLEAN,
                    next_run_at DATETIME,
                    overlap_policy VARCHAR(16),
                    catch_up_policy VARCHAR(16),
                    last_triggered_at DATETIME
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
                "(id, vendor, product, version_match, status, note) VALUES "
                "('e1', 'OpenSSH', 'OpenSSH', '7.*', 'invalid', 'EOL'), "
                "('e2', 'OpenSSH', 'OpenSSH', '9.*', 'valid', NULL), "
                "('e3', 'Acme', 'Widget', '1.0', 'invalid', 'bad')"
            )
        )
    engine.dispose()


def test_migration_0004_derives_threshold_and_flags_invalid_only(tmp_path, monkeypatch):
    db_path = tmp_path / "pre_v07.sqlite3"
    db_url = f"sqlite:///{db_path.as_posix()}"
    _build_pre_v07_schema(db_url)

    monkeypatch.setattr(app_settings, "database_url", db_url)

    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    command.upgrade(cfg, "0004_version_dictionary_overhaul")

    engine = sa.create_engine(db_url)
    with engine.connect() as conn:
        rows = conn.execute(
            sa.text(
                "SELECT vendor, product, min_version, needs_review FROM reference_version_entries"
            )
        ).fetchall()
    engine.dispose()

    by_product = {r.product: r for r in rows}
    assert len(rows) == 2  # OpenSSH's two legacy rows collapsed into one

    openssh = by_product["OpenSSH"]
    assert openssh.min_version == "9.0"
    assert not openssh.needs_review

    widget = by_product["Widget"]
    assert widget.min_version is None
    assert widget.needs_review

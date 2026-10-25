"""Create the database schema (idempotent) — the fresh-install path.

Usage:
    python -m asset_dashboard.db.init

This is THE way to create a brand-new `data/app.sqlite3`: `create_all`
builds the schema straight from the current ORM models — i.e. the final,
already-correct structure — rather than replaying the Alembic migration
chain from an empty database. That chain is NOT fresh-install-safe: early
migrations (e.g. `0002_feature_002`) only ever ALTER tables that already
exist, on the long-standing assumption that this `db.init` step (not
`alembic upgrade head`) laid down the feature-001 baseline tables first.
Running `alembic upgrade head` against a genuinely empty database skips
that baseline and dies on the first migration that assumes a table like
`schedules` is already there (`NoSuchTableError`).

Use this for a from-scratch deployment, before `seed_reference` and
`auth.create_account` (see README's Quick start). For upgrading an
EXISTING, already-running deployment to a newer version, use `alembic
upgrade head` instead (see README's "Upgrading an existing database") —
never run this against a database you intend to keep upgrading via
Alembic afterward without understanding `_stamp_alembic_head` below.

`create_all` does NOT add new columns to tables that already exist, so
`_add_missing_columns` performs the tiny additive migrations this project
needs (feature 008): check `PRAGMA table_info` and `ALTER TABLE … ADD
COLUMN` for each new nullable/JSON-defaulted column when it is absent.
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from asset_dashboard.db import models  # noqa: F401  (register all models on Base.metadata)
from asset_dashboard.db.base import Base, engine

# Feature 008 additive columns, per table. Each is a plain nullable column
# (SQLite can add a single column with a constant/NULL default). FK-bearing
# columns are added WITHOUT the FK constraint on pre-existing tables —
# SQLite cannot add a constraint to an existing column — which is acceptable
# because the app also nulls references defensively (feature-007 delete fix).
_MISSING_COLUMNS: dict[str, dict[str, str]] = {
    "default_credential_entries": {
        "probe_config": "JSON",
    },
    "tool_tasks": {
        "dictionary_id": "VARCHAR(36)",
        "attempt_ceiling": "INTEGER",
    },
    "tool_check_runs": {
        "dictionary_id": "VARCHAR(36)",
        "attempt_ceiling": "INTEGER",
        "error_detail": "TEXT",
    },
}


def _add_missing_columns() -> None:
    """Idempotently add feature-008 columns to pre-existing tables."""
    with engine.begin() as conn:
        for table, columns in _MISSING_COLUMNS.items():
            existing = {
                row[1]  # PRAGMA table_info: (cid, name, type, notnull, dflt, pk)
                for row in conn.execute(text(f"PRAGMA table_info({table})"))
            }
            if not existing:
                continue  # table doesn't exist yet — create_all handled it
            for column, column_type in columns.items():
                if column not in existing:
                    conn.execute(
                        text(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")
                    )


def _stamp_alembic_head() -> None:
    """Record this freshly created schema as already being at Alembic's
    latest revision. Without this, the database has no `alembic_version`
    row at all, so a later `alembic upgrade head` (run when upgrading this
    deployment to a future version) would try to replay the ENTIRE
    migration chain from scratch against tables that already exist —
    the mirror image of the NoSuchTableError this module exists to avoid.
    """
    from alembic.command import stamp
    from alembic.config import Config

    project_root = Path(__file__).resolve().parents[3]
    cfg = Config(str(project_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(project_root / "migrations"))
    stamp(cfg, "head")


def main() -> None:
    Base.metadata.create_all(engine)
    _add_missing_columns()
    _stamp_alembic_head()
    print("Database schema is up to date.")


if __name__ == "__main__":
    main()

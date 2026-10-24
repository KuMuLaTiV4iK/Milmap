"""Create the database schema (idempotent).

Usage:
    python -m asset_dashboard.db.init

For a from-scratch deployment this is the step before `seed_reference`
and `auth.create_account` (see quickstart.md). It is safe to re-run —
`create_all` only creates tables that don't already exist, it never
drops or alters existing ones (use a real Alembic migration for that).

`create_all` does NOT add new columns to tables that already exist, so
`_add_missing_columns` performs the tiny additive migrations this project
needs (feature 008): check `PRAGMA table_info` and `ALTER TABLE … ADD
COLUMN` for each new nullable/JSON-defaulted column when it is absent.
"""
from __future__ import annotations

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


def main() -> None:
    Base.metadata.create_all(engine)
    _add_missing_columns()
    print("Database schema is up to date.")


if __name__ == "__main__":
    main()

"""SQLAlchemy engine/session setup (SQLite, WAL mode).

WAL mode improves concurrent read/write behavior for the "a few concurrent
operators" scale this project targets (spec Assumption: Concurrency).
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from asset_dashboard.config import DATA_DIR, settings

DATA_DIR.mkdir(parents=True, exist_ok=True)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _set_sqlite_pragmas(dbapi_connection, connection_record) -> None:  # noqa: ANN001
    """Enable WAL mode + foreign keys on every new SQLite connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def configure_sqlite_pragmas(target_engine: Engine) -> None:
    """Register the pragma listener on a given engine. Used for the
    module-level engine below AND by tests that swap in a fresh engine
    (an engine-less listener registration would silently no-op FK
    enforcement, e.g. ON DELETE SET NULL, for that engine's connections)."""
    event.listen(target_engine, "connect", _set_sqlite_pragmas)


engine: Engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    future=True,
)
configure_sqlite_pragmas(engine)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a request-scoped session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Context manager for non-request code paths (scheduler jobs, CLI scripts)."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

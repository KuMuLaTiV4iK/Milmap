"""Shared pytest fixtures: an isolated app + DB + session store per test.

IMPORTANT: never touch the real `data/` directory from here. The DB engine
and the session-signing secret key are both process-wide singletons
created at import time (see db/base.py and auth/sessions.py) — if a test
doesn't explicitly swap them out, it silently reads/writes the real
on-disk database and the real secret key (which, once the app has real
users, is live production state: deleting or reusing it would invalidate
real session cookies). Every fixture below swaps BOTH out per test.
"""

from __future__ import annotations

import secrets
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture()
def client(monkeypatch, tmp_path) -> Iterator[TestClient]:
    """A TestClient backed by a fresh, isolated SQLite file + session store per test."""
    db_path = tmp_path / "test.sqlite3"
    db_url = f"sqlite:///{db_path.as_posix()}"

    monkeypatch.setenv("ASSET_DASHBOARD_DATABASE_URL", db_url)

    import asset_dashboard.db.base as db_base

    test_engine = create_engine(db_url, connect_args={"check_same_thread": False}, future=True)
    db_base.configure_sqlite_pragmas(test_engine)  # WAL + FK enforcement, same as production
    db_base.engine = test_engine
    db_base.SessionLocal = sessionmaker(
        bind=test_engine, autoflush=False, autocommit=False, future=True
    )

    from asset_dashboard.db import models  # noqa: F401  (register all models on Base)

    db_base.Base.metadata.create_all(test_engine)

    # Fresh, isolated session store with a random in-memory key — never the
    # real on-disk secret, and never shared session state across tests.
    import asset_dashboard.auth.sessions as sessions_module
    from asset_dashboard.config import settings

    sessions_module.session_store = sessions_module.SessionStore(
        idle_timeout_seconds=settings.session_idle_timeout_seconds,
        secret_key=secrets.token_urlsafe(32),
    )

    # Don't start the real background scheduler heartbeat for ordinary
    # HTTP-driven tests: scheduling.engine.tick() is designed to be called
    # directly and deterministically (see test_us5_schedule.py), and
    # starting/stopping a real BackgroundScheduler on every single test —
    # ~90 times in a short run — risks a job still executing when
    # shutdown(wait=False) returns, which can then write into the NEXT
    # test's (different) database after this one is torn down.
    import asset_dashboard.scheduling.engine as scheduling_engine

    monkeypatch.setattr(scheduling_engine, "start_scheduler", lambda *a, **k: None)
    monkeypatch.setattr(scheduling_engine, "shutdown_scheduler", lambda *a, **k: None)

    from asset_dashboard.main import create_app

    app = create_app()

    with TestClient(app) as test_client:
        yield test_client

    db_base.Base.metadata.drop_all(test_engine)


@pytest.fixture()
def bootstrap_account():
    """Create an operator account directly (bypassing HTTP), simulating the CLI bootstrap."""

    def _create(
        username: str = "bootstrap_admin",
        password: str = "a-very-long-and-strong-password",
    ):
        from asset_dashboard.auth.passwords import hash_password
        from asset_dashboard.db.base import session_scope
        from asset_dashboard.db.models import OperatorAccount

        with session_scope() as session:
            account = OperatorAccount(username=username, password_hash=hash_password(password))
            session.add(account)
            session.flush()
            return account.id, username, password

    return _create


@pytest.fixture()
def authed_client(client, bootstrap_account) -> TestClient:
    """A TestClient that already holds a valid session cookie (Operator role)."""
    _id, username, password = bootstrap_account()
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return client


@pytest.fixture()
def bootstrap_admin_account():
    """Create an Administrator-role account directly (bypassing HTTP), for
    feature-002 role-gated tests."""

    def _create(
        username: str = "bootstrap_root_admin",
        password: str = "an-even-longer-and-stronger-password",
    ):
        from asset_dashboard.auth.passwords import hash_password
        from asset_dashboard.db.base import session_scope
        from asset_dashboard.db.models import OperatorAccount, OperatorAccountRole

        with session_scope() as session:
            account = OperatorAccount(
                username=username,
                password_hash=hash_password(password),
                role=OperatorAccountRole.ADMINISTRATOR,
            )
            session.add(account)
            session.flush()
            return account.id, username, password

    return _create


@pytest.fixture()
def admin_client(client, bootstrap_admin_account) -> TestClient:
    """A TestClient that already holds a valid session cookie (Administrator role)."""
    _id, username, password = bootstrap_admin_account()
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return client


@pytest.fixture()
def second_client(client) -> Iterator[TestClient]:
    """A second TestClient bound to the SAME app/DB as `client`, with its
    own independent cookie jar — for tests that need two signed-in actors
    at once (e.g. an admin acting on a second user's live session), since
    `client` and any fixture built on it (`authed_client`, `admin_client`)
    all share one cookie jar and would otherwise clobber each other's
    session on login."""
    with TestClient(client.app) as other:
        yield other

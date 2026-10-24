"""Unit tests for the shared row-count-based archival helper
(archival.py): archives the oldest rows once a table's non-archived
count exceeds a threshold — never deletes."""
from __future__ import annotations

from asset_dashboard.archival import archive_oldest
from asset_dashboard.db.base import session_scope
from asset_dashboard.db.models import DiscoveryRun


def _make_run(session, index: int) -> DiscoveryRun:
    from datetime import timedelta

    from asset_dashboard.db.models import utcnow

    run = DiscoveryRun(started_at=utcnow() - timedelta(minutes=1000 - index))
    session.add(run)
    return run


def test_archive_oldest_noop_under_threshold(client):
    with session_scope() as session:
        for i in range(10):
            _make_run(session, i)

    with session_scope() as session:
        archived_count = archive_oldest(
            session, DiscoveryRun, DiscoveryRun.started_at, threshold=100, batch=50
        )
    assert archived_count == 0

    with session_scope() as session:
        assert session.query(DiscoveryRun).filter_by(archived=False).count() == 10


def test_archive_oldest_archives_oldest_batch_over_threshold(client):
    with session_scope() as session:
        for i in range(101):
            _make_run(session, i)

    with session_scope() as session:
        archived_count = archive_oldest(
            session, DiscoveryRun, DiscoveryRun.started_at, threshold=100, batch=50
        )
    assert archived_count == 50

    with session_scope() as session:
        assert session.query(DiscoveryRun).filter_by(archived=False).count() == 51
        assert session.query(DiscoveryRun).filter_by(archived=True).count() == 50
        # Archived rows are the oldest ones, never deleted.
        assert session.query(DiscoveryRun).count() == 101
        oldest_still_active = (
            session.query(DiscoveryRun)
            .filter_by(archived=False)
            .order_by(DiscoveryRun.started_at.asc())
            .first()
        )
        newest_archived = (
            session.query(DiscoveryRun)
            .filter_by(archived=True)
            .order_by(DiscoveryRun.started_at.desc())
            .first()
        )
        assert newest_archived.started_at < oldest_still_active.started_at


def test_archive_oldest_is_idempotent_per_call(client):
    with session_scope() as session:
        for i in range(101):
            _make_run(session, i)

    with session_scope() as session:
        archive_oldest(session, DiscoveryRun, DiscoveryRun.started_at, threshold=100, batch=50)

    # A second call with the same threshold: 51 active rows is already
    # under threshold, so nothing more is archived.
    with session_scope() as session:
        archived_count = archive_oldest(
            session, DiscoveryRun, DiscoveryRun.started_at, threshold=100, batch=50
        )
    assert archived_count == 0

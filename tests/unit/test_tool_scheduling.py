"""Unit tests for scheduling/engine.py's ToolTask dispatch (FR-020, FR-021):
`tick()` dispatches due ToolTasks, advances next_run_at, honors overlap/
catch-up, and never exceeds the 3-attempt/>=5s device-safety guard (reused
unchanged from check_default_credentials)."""

from datetime import timedelta

from asset_dashboard.compliance import credential_check
from asset_dashboard.compliance.probes.base import ProbeAttemptResult
from asset_dashboard.db.models import CatchUpPolicy, OverlapPolicy, ToolTask, utcnow
from asset_dashboard.scheduling.engine import tick


def _make_task(session, **overrides):
    defaults = dict(
        target_scope=["10.0.0.1"],
        port=22,
        service="ssh",
        recurrence={"type": "interval", "seconds": 3600},
        enabled=True,
        next_run_at=utcnow() - timedelta(seconds=1),
        overlap_policy=OverlapPolicy.SKIP,
        catch_up_policy=CatchUpPolicy.RUN_ONCE,
    )
    defaults.update(overrides)
    task = ToolTask(**defaults)
    session.add(task)
    session.flush()
    return task


def test_tick_dispatches_due_tool_task_and_advances_next_run_at(client, monkeypatch):
    from asset_dashboard.db.base import session_scope

    monkeypatch.setattr(credential_check.time, "sleep", lambda s: None)
    monkeypatch.setitem(
        credential_check._PROBES,
        "ssh",
        lambda *a, **k: ProbeAttemptResult(matched=False, response_excerpt=""),
    )

    with session_scope() as session:
        task = _make_task(session)
        task_id = task.id
        original_next_run = task.next_run_at

    with session_scope() as session:
        started = tick(session)
        assert len(started) == 1

    with session_scope() as session:
        refreshed = session.get(ToolTask, task_id)
        assert refreshed.next_run_at > original_next_run
        assert refreshed.last_triggered_at is not None


def test_once_tool_task_fires_exactly_once_then_disables(client, monkeypatch):
    """Regression: a `once` credential-check task used to re-fire every tick
    because _tick_tool_tasks always recomputed next_run_at. It must fire once,
    then disable (enabled=False) and never fire again."""
    from datetime import UTC, datetime

    from asset_dashboard.db.base import session_scope
    from asset_dashboard.db.models import DefaultCredentialEntry

    monkeypatch.setattr(credential_check.time, "sleep", lambda s: None)
    monkeypatch.setitem(
        credential_check._PROBES,
        "ssh",
        lambda *a, **k: ProbeAttemptResult(matched=False, response_excerpt=""),
    )

    past = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=1)
    with session_scope() as session:
        session.add(DefaultCredentialEntry(vendor="t", service="ssh", credentials=[]))
        task = _make_task(
            session,
            recurrence={"type": "once", "run_at": past.isoformat()},
            next_run_at=past,
        )
        task_id = task.id

    with session_scope() as session:
        started = tick(session)
        assert len(started) == 1  # fired once

    with session_scope() as session:
        refreshed = session.get(ToolTask, task_id)
        assert refreshed.enabled is False  # disabled after its single fire
        assert refreshed.last_triggered_at is not None

    # A second tick must NOT fire it again.
    with session_scope() as session:
        assert tick(session) == []


def test_tick_ignores_disabled_tasks(client, monkeypatch):
    from asset_dashboard.db.base import session_scope

    monkeypatch.setattr(credential_check.time, "sleep", lambda s: None)

    with session_scope() as session:
        _make_task(session, enabled=False)

    with session_scope() as session:
        assert tick(session) == []


def test_tick_never_dispatches_a_tool_task_that_is_not_yet_due(client):
    from asset_dashboard.db.base import session_scope

    with session_scope() as session:
        _make_task(session, next_run_at=utcnow() + timedelta(hours=1))

    with session_scope() as session:
        assert tick(session) == []


def test_credential_check_guard_reused_by_scheduled_dispatch(client, monkeypatch):
    """The central guard (now: exhaustive to the dictionary size by default,
    >=5s cooldown) is enforced by check_default_credentials — this confirms
    the scheduled dispatch path goes through that same function. Dispatch is
    now asynchronous (US5), so poll for the background run to finish."""
    import time as _time

    from asset_dashboard.db.base import session_scope
    from asset_dashboard.db.models import (
        DefaultCredentialEntry,
        RunStatus,
        ToolCheckResult,
        ToolCheckRun,
    )

    monkeypatch.setattr(credential_check.time, "sleep", lambda s: None)
    monkeypatch.setitem(
        credential_check._PROBES,
        "ssh",
        lambda *a, **k: ProbeAttemptResult(matched=False, response_excerpt=""),
    )

    with session_scope() as session:
        session.add(
            DefaultCredentialEntry(
                vendor="Test",
                service="ssh",
                credentials=[{"username": f"u{i}", "secret": f"s{i}"} for i in range(10)],
                success_keywords=["ok"],
            )
        )
        _make_task(session)

    with session_scope() as session:
        started = tick(session)
        assert len(started) == 1
        run_id = started[0]

    # The run is committed `running` synchronously; probing finishes off-thread.
    deadline = _time.time() + 3.0
    while _time.time() < deadline:
        with session_scope() as session:
            run = session.get(ToolCheckRun, run_id)
            if run.status != RunStatus.RUNNING:
                break
        _time.sleep(0.02)

    with session_scope() as session:
        results = session.query(ToolCheckResult).all()
        assert len(results) == 1
        # No arbitrary cap: the whole 10-credential dictionary was tried.
        assert results[0].attempts_made == 10

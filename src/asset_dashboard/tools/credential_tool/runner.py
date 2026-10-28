"""Background orchestrator for credential-tool runs (US5, FR-112/FR-117).

Deliberately parallel to `discovery/runner.py`: a module lock + a registry
of currently-running run ids, and one daemon thread per run. The run row is
committed as `running` BEFORE the thread starts, so the triggering request
returns immediately and the run is observable in history right away; the
finishers set `completed` or `failed` (with `error_detail`) in a fresh
`session_scope` and clear the registry.

This is NOT a second scheduler (constitution Principle VI preserved):
scheduling stays single-engine (scheduling/engine.py); this module only
executes an already-decided run asynchronously. The credential-check
lifecycle differs from an nmap scan (no subprocess, internal cooldown loop,
no profile concurrency key), which is why it does not reuse
discovery/runner.py directly — see plan.md Complexity Tracking.
"""

from __future__ import annotations

import threading

from sqlalchemy.orm import Session

from asset_dashboard.archival import archive_oldest
from asset_dashboard.db.base import session_scope
from asset_dashboard.db.models import RunStatus, RunTrigger, ToolCheckRun, utcnow
from asset_dashboard.tools.credential_tool.service import execute_check

_lock = threading.Lock()
_running_run_ids: set[str] = set()


def is_run_running(run_id: str) -> bool:
    with _lock:
        return run_id in _running_run_ids


def start_run(
    session: Session,
    *,
    target_scope: list[str],
    port: int,
    service: str,
    dictionary_id: str | None = None,
    attempt_ceiling: int | None = None,
    trigger: RunTrigger = RunTrigger.MANUAL,
    triggered_by_id: str | None = None,
    tool_task_id: str | None = None,
) -> ToolCheckRun:
    """Create the run as `running`, commit it, and probe on a daemon thread."""
    run = ToolCheckRun(
        tool_task_id=tool_task_id,
        trigger=trigger,
        triggered_by_id=triggered_by_id,
        target_scope=list(target_scope),
        port=port,
        service=service,
        status=RunStatus.RUNNING,
        dictionary_id=dictionary_id,
        attempt_ceiling=attempt_ceiling,
    )
    session.add(run)
    session.flush()
    run_id = run.id
    session.commit()

    with _lock:
        _running_run_ids.add(run_id)

    thread = threading.Thread(
        target=_execute_run,
        args=(run_id, dictionary_id, attempt_ceiling, triggered_by_id),
        daemon=True,
    )
    thread.start()
    return run


def _execute_run(
    run_id: str,
    dictionary_id: str | None,
    attempt_ceiling: int | None,
    triggered_by_id: str | None,
) -> None:
    try:
        with session_scope() as session:
            run = session.get(ToolCheckRun, run_id)
            execute_check(
                session,
                run,
                dictionary_id=dictionary_id,
                attempt_ceiling=attempt_ceiling,
                triggered_by_id=triggered_by_id,
            )
            run.status = RunStatus.COMPLETED
            run.finished_at = utcnow()
            session.flush()
            archive_oldest(session, ToolCheckRun, ToolCheckRun.started_at)
    except Exception as exc:  # noqa: BLE001 - any worker failure must mark the run failed
        _finish_failed(run_id, str(exc))
    finally:
        with _lock:
            _running_run_ids.discard(run_id)


def _finish_failed(run_id: str, error_detail: str) -> None:
    """Mark a background run failed so it never stays stuck `running` (FR-117)."""
    with session_scope() as session:
        run = session.get(ToolCheckRun, run_id)
        if run is None:
            return
        run.status = RunStatus.FAILED
        run.error_detail = error_detail
        run.finished_at = utcnow()

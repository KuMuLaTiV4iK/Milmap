"""Dispatch a scheduled ToolTask to the credential-tool service (FR-021).

Called from scheduling/engine.tick() — produces a ToolCheckRun equivalent
in shape/outcome to an on-demand run (same service.run_credential_check).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from asset_dashboard.db.models import RunTrigger, ToolCheckRun, ToolTask
from asset_dashboard.tools.credential_tool import runner


def dispatch_tool_task(session: Session, task: ToolTask) -> ToolCheckRun:
    """Dispatch a scheduled task through the background runner (US5): the run
    is committed as `running` and probing happens off-thread, equivalent to an
    on-demand run."""
    return runner.start_run(
        session,
        target_scope=task.target_scope,
        port=task.port,
        service=task.service,
        dictionary_id=task.dictionary_id,
        attempt_ceiling=task.attempt_ceiling,
        trigger=RunTrigger.SCHEDULED,
        triggered_by_id=None,
        tool_task_id=task.id,
    )


def has_running_run(session: Session, task_id: str) -> bool:
    """True iff a ToolCheckRun for this task is currently RUNNING — used by
    the scheduler to honor overlap_policy (no duplicate concurrent run of
    the same tool task, consistent with Schedule's FR-043 guarantee)."""
    from asset_dashboard.db.models import RunStatus  # noqa: PLC0415

    return (
        session.query(ToolCheckRun)
        .filter(ToolCheckRun.tool_task_id == task_id, ToolCheckRun.status == RunStatus.RUNNING)
        .count()
        > 0
    )

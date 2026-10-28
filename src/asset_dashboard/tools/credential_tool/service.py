"""Standalone default-credential tool — the probing loop body (FR-020-FR-025).

Decoupled from discovery-profile runs entirely (FR-020). The loop body
(`execute_check`) is callable both synchronously (`run_credential_check`,
kept for direct/unit use) and from the background worker in `runner.py`
(US5), so an on-demand and a scheduled run are equivalent in shape and
outcome. Every path reuses the central guard in
`compliance/credential_check.py` (>=5s cooldown NON-NEGOTIABLE; attempt
ceiling configurable, default = dictionary size — constitution v2.0.0).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from asset_dashboard.archival import archive_oldest
from asset_dashboard.audit.log import record_event
from asset_dashboard.compliance.credential_check import check_default_credentials
from asset_dashboard.db.models import (
    AuditEventType,
    ComplianceResult,
    RunStatus,
    RunTrigger,
    ToolCheckResult,
    ToolCheckRun,
    utcnow,
)

_RESULT_MAP = {
    "compliant": ComplianceResult.COMPLIANT,
    "non_compliant": ComplianceResult.NON_COMPLIANT,
    "inconclusive": ComplianceResult.INCONCLUSIVE,
}


def execute_check(
    session: Session,
    run: ToolCheckRun,
    *,
    dictionary_id: str | None = None,
    attempt_ceiling: int | None = None,
    triggered_by_id: str | None = None,
) -> dict[str, int]:
    """Probe every target in `run.target_scope` and persist per-target results.

    Does NOT change `run.status` or commit — the caller (synchronous
    `run_credential_check` or the background `runner`) owns the lifecycle.
    Returns the result tally (also stored on `run.summary`).
    """
    tally: dict[str, int] = {}
    for address in run.target_scope:
        outcome = check_default_credentials(
            session,
            address,
            run.port,
            run.service,
            dictionary_id=dictionary_id,
            ceiling=attempt_ceiling,
        )
        result = _RESULT_MAP[outcome.result]
        session.add(
            ToolCheckResult(
                run_id=run.id,
                address=address,
                result=result,
                attempts_made=outcome.attempts_made,
                # Password-free per-attempt detail (FR-114): usernames, status
                # codes and body-only excerpts only — never the attempted secret.
                detail={
                    "protocol": outcome.protocol,
                    "matched_username": outcome.matched_username,
                    "matched_dictionary_entry": outcome.matched_dictionary_entry,
                    "attempts": outcome.attempts,
                },
            )
        )
        tally[result.value] = tally.get(result.value, 0) + 1
        record_event(
            session,
            AuditEventType.TOOL_CHECK,
            actor_id=triggered_by_id,
            # Attempt count/protocol/result + matched USERNAME only — never a
            # secret and never the per-attempt excerpts (FR-039/FR-114).
            detail={
                "run_id": run.id,
                "address": address,
                "protocol": outcome.protocol,
                "attempts_made": outcome.attempts_made,
                "result": outcome.result,
                "matched_username": outcome.matched_username,
            },
        )
    run.summary = tally
    return tally


def run_credential_check(
    session: Session,
    *,
    target_scope: list[str],
    port: int,
    service: str,
    trigger: RunTrigger = RunTrigger.MANUAL,
    triggered_by_id: str | None = None,
    tool_task_id: str | None = None,
    dictionary_id: str | None = None,
    attempt_ceiling: int | None = None,
) -> ToolCheckRun:
    """Run the guarded default-credential check synchronously against every
    target. The asynchronous (background-thread) path lives in `runner.py`;
    this synchronous entry point is retained for direct/unit invocation."""
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
    return run

"""Standalone credential-tool routes (FR-020-FR-025). See contracts/http-api-delta.md."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from asset_dashboard.audit.log import record_event
from asset_dashboard.auth.authz import require_operator, session_context
from asset_dashboard.db.base import get_session
from asset_dashboard.db.models import (
    AuditEventType,
    CatchUpPolicy,
    DefaultCredentialEntry,
    OperatorAccount,
    OverlapPolicy,
    RunTrigger,
    ToolCheckRun,
    ToolTask,
    utcnow,
)
from asset_dashboard.scheduling.engine import compute_next_run_at, validate_recurrence
from asset_dashboard.tools.credential_tool import runner
from asset_dashboard.web.errors import api_error, validation_error
from asset_dashboard.web.templating import templates

router = APIRouter(prefix="/api/tools/credential-check")
pages_router = APIRouter()

ALLOWED_SERVICES = {"sip", "ssh", "http", "https", "telnet", "ftp", "routeros-api"}


class RunNowIn(BaseModel):
    target_scope: list[str] = Field(default_factory=list)
    port: int
    service: str
    dictionary_id: str | None = None
    attempt_ceiling: int | None = None


class TaskIn(BaseModel):
    target_scope: list[str] = Field(default_factory=list)
    port: int
    service: str
    recurrence: dict
    enabled: bool = True
    overlap_policy: OverlapPolicy = OverlapPolicy.SKIP
    catch_up_policy: CatchUpPolicy = CatchUpPolicy.RUN_ONCE
    dictionary_id: str | None = None
    attempt_ceiling: int | None = None


class CredentialPairIn(BaseModel):
    username: str
    secret: str


class CredentialListIn(BaseModel):
    """A per-service default-credential list (FR-036, FR-040). `credentials`
    is the catalog of factory-default pairs the guarded check will try for
    this service — reference data, never a log of attempts. `probe_config`
    holds optional HTTP/HTTPS form-probe settings (feature 008)."""

    vendor: str
    service: str
    credentials: list[CredentialPairIn] = Field(default_factory=list)
    success_keywords: list[str] = Field(default_factory=list)
    probe_config: dict = Field(default_factory=dict)


class TaskUpdateIn(BaseModel):
    target_scope: list[str] | None = None
    port: int | None = None
    service: str | None = None
    recurrence: dict | None = None
    enabled: bool | None = None
    overlap_policy: OverlapPolicy | None = None
    catch_up_policy: CatchUpPolicy | None = None
    dictionary_id: str | None = None
    attempt_ceiling: int | None = None


def _validate_run_params(target_scope: list[str], service: str) -> dict[str, str]:
    errors: dict[str, str] = {}
    if not target_scope:
        errors["target_scope"] = "target_scope must include at least one host."
    if service not in ALLOWED_SERVICES:
        errors["service"] = f"service must be one of {sorted(ALLOWED_SERVICES)}"
    return errors


def _serialize_run(run: ToolCheckRun) -> dict:
    return {
        "id": run.id,
        "tool_task_id": run.tool_task_id,
        "trigger": run.trigger.value,
        "target_scope": run.target_scope,
        "port": run.port,
        "service": run.service,
        "status": run.status.value,
        "dictionary_id": run.dictionary_id,
        "attempt_ceiling": run.attempt_ceiling,
        "error_detail": run.error_detail,
        "started_at": run.started_at.isoformat(),
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "summary": run.summary,
    }


def _serialize_run_detail(run: ToolCheckRun) -> dict:
    return {
        **_serialize_run(run),
        "results": [
            {
                "address": r.address,
                "result": r.result.value,
                "attempts_made": r.attempts_made,
                # Per-attempt data for the result table (FR-113), password-free
                # (FR-114): usernames, status codes and body-only excerpts only.
                "matched_username": r.detail.get("matched_username"),
                "matched_dictionary_entry": r.detail.get("matched_dictionary_entry"),
                "attempts": r.detail.get("attempts", []),
                "detail": r.detail,
            }
            for r in run.results
        ],
    }


def _serialize_task(task: ToolTask) -> dict:
    return {
        "id": task.id,
        "tool": task.tool.value,
        "target_scope": task.target_scope,
        "port": task.port,
        "service": task.service,
        "recurrence": task.recurrence,
        "enabled": task.enabled,
        "next_run_at": task.next_run_at.isoformat(),
        "overlap_policy": task.overlap_policy.value,
        "catch_up_policy": task.catch_up_policy.value,
        "last_triggered_at": task.last_triggered_at.isoformat() if task.last_triggered_at else None,
        "dictionary_id": task.dictionary_id,
        "attempt_ceiling": task.attempt_ceiling,
    }


def _serialize_credential_list(entry: DefaultCredentialEntry) -> dict:
    return {
        "id": entry.id,
        "vendor": entry.vendor,
        "service": entry.service,
        "credentials": [
            {"username": c.get("username", ""), "secret": c.get("secret", "")}
            for c in entry.credentials
        ],
        "success_keywords": list(entry.success_keywords),
        "probe_config": entry.probe_config or {},
    }


@router.post("", status_code=201)
def api_run_now(
    body: RunNowIn,
    session: Session = Depends(get_session),
    account: OperatorAccount = Depends(require_operator),
):
    errors = _validate_run_params(body.target_scope, body.service)
    if errors:
        return validation_error(errors)

    # US2/FR-104: the operator must choose one dictionary per run. If none
    # exists for the service, guide them to create one first; if one exists
    # but none (or an unknown one) was chosen, require a valid selection.
    if body.service in ALLOWED_SERVICES:
        dicts = session.query(DefaultCredentialEntry).filter_by(service=body.service).all()
        if not dicts:
            return validation_error(
                {
                    "dictionary_id": (
                        "No credential dictionary exists for this service — create one first."
                    )
                }
            )
        if body.dictionary_id is None or not any(d.id == body.dictionary_id for d in dicts):
            return validation_error(
                {"dictionary_id": "Select a credential dictionary for this service."}
            )

    # Start asynchronously (FR-112): the run is committed as `running` and
    # probing happens off-thread, so this returns immediately.
    run = runner.start_run(
        session,
        target_scope=body.target_scope,
        port=body.port,
        service=body.service,
        dictionary_id=body.dictionary_id,
        attempt_ceiling=body.attempt_ceiling,
        trigger=RunTrigger.MANUAL,
        triggered_by_id=account.id,
    )
    return {"run_id": run.id, "status": run.status.value}


@router.get("/runs")
def api_list_runs(
    include_archived: bool = False,
    session: Session = Depends(get_session),
    _account: OperatorAccount = Depends(require_operator),
):
    query = session.query(ToolCheckRun).order_by(ToolCheckRun.started_at.desc())
    if not include_archived:
        query = query.filter(ToolCheckRun.archived.is_(False))
    return [_serialize_run(r) for r in query.all()]


@router.get("/runs/{run_id}")
def api_get_run(
    run_id: str,
    session: Session = Depends(get_session),
    _account: OperatorAccount = Depends(require_operator),
):
    run = session.get(ToolCheckRun, run_id)
    if run is None:
        return JSONResponse(status_code=404, content=api_error("not_found", "Run not found."))
    return _serialize_run_detail(run)


@router.get("/tasks")
def api_list_tasks(
    session: Session = Depends(get_session),
    _account: OperatorAccount = Depends(require_operator),
):
    tasks = session.query(ToolTask).all()
    return [_serialize_task(t) for t in tasks]


@router.post("/tasks", status_code=201)
def api_create_task(
    body: TaskIn,
    session: Session = Depends(get_session),
    account: OperatorAccount = Depends(require_operator),
):
    errors = _validate_run_params(body.target_scope, body.service)
    if errors:
        return validation_error(errors)

    try:
        now = utcnow()
        validate_recurrence(body.recurrence, now=now)
        next_run_at = compute_next_run_at(body.recurrence, now)
    except Exception as exc:  # noqa: BLE001 - surfaced to the caller as a validation error
        return validation_error({"recurrence": str(exc)})

    task = ToolTask(
        target_scope=body.target_scope,
        port=body.port,
        service=body.service,
        recurrence=body.recurrence,
        enabled=body.enabled,
        next_run_at=next_run_at,
        overlap_policy=body.overlap_policy,
        catch_up_policy=body.catch_up_policy,
        dictionary_id=body.dictionary_id,
        attempt_ceiling=body.attempt_ceiling,
        created_by=account.id,
    )
    session.add(task)
    record_event(
        session,
        AuditEventType.SCHEDULE_CHANGE,
        actor_id=account.id,
        detail={"action": "create_tool_task", "task_id_pending": True},
    )
    session.commit()
    return _serialize_task(task)


@router.put("/tasks/{task_id}")
def api_update_task(
    task_id: str,
    body: TaskUpdateIn,
    session: Session = Depends(get_session),
    account: OperatorAccount = Depends(require_operator),
):
    task = session.get(ToolTask, task_id)
    if task is None:
        return JSONResponse(status_code=404, content=api_error("not_found", "Task not found."))

    if body.target_scope is not None:
        task.target_scope = body.target_scope
    if body.port is not None:
        task.port = body.port
    if body.service is not None:
        task.service = body.service
    if body.recurrence is not None:
        try:
            now = utcnow()
            validate_recurrence(body.recurrence, now=now)
            task.next_run_at = compute_next_run_at(body.recurrence, now)
        except Exception as exc:  # noqa: BLE001
            return validation_error({"recurrence": str(exc)})
        task.recurrence = body.recurrence
    if body.enabled is not None:
        task.enabled = body.enabled
    if body.overlap_policy is not None:
        task.overlap_policy = body.overlap_policy
    if body.catch_up_policy is not None:
        task.catch_up_policy = body.catch_up_policy
    if body.dictionary_id is not None:
        task.dictionary_id = body.dictionary_id
    if body.attempt_ceiling is not None:
        task.attempt_ceiling = body.attempt_ceiling

    session.add(task)
    record_event(
        session,
        AuditEventType.SCHEDULE_CHANGE,
        actor_id=account.id,
        detail={"action": "update_tool_task", "task_id": task.id},
    )
    session.commit()
    return _serialize_task(task)


@router.delete("/tasks/{task_id}", status_code=204)
def api_delete_task(
    task_id: str,
    session: Session = Depends(get_session),
    account: OperatorAccount = Depends(require_operator),
):
    task = session.get(ToolTask, task_id)
    if task is None:
        return JSONResponse(status_code=404, content=api_error("not_found", "Task not found."))
    # Detach the task's historical runs before deleting it: a ToolCheckRun
    # references the task via a FK, so deleting the task directly fails the
    # FK constraint. Runs survive their task (mirroring how a DiscoveryRun
    # survives its profile) — keep them, just null out the back-reference.
    session.query(ToolCheckRun).filter(ToolCheckRun.tool_task_id == task_id).update(
        {ToolCheckRun.tool_task_id: None}, synchronize_session=False
    )
    session.delete(task)
    record_event(
        session,
        AuditEventType.SCHEDULE_CHANGE,
        actor_id=account.id,
        detail={"action": "delete_tool_task", "task_id": task_id},
    )
    session.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Per-service default-credential list management (FR-036, FR-040).
#
# The guarded check (compliance/credential_check.py) already selects
# candidates per service via DefaultCredentialEntry.filter_by(service=...).
# These endpoints let an operator maintain a distinct credential list for
# each service from the UI, instead of only re-seeding from JSON. Audit
# detail records service/vendor/counts ONLY — never an attempted secret
# (FR-039): the audit helper additionally rejects secret-like keys.
# ---------------------------------------------------------------------------


@router.get("/credentials")
def api_list_credential_lists(
    service: str | None = None,
    session: Session = Depends(get_session),
    _account: OperatorAccount = Depends(require_operator),
):
    query = session.query(DefaultCredentialEntry)
    if service is not None:
        # Optional filter for the per-service dictionary selector (US2, 3.2).
        query = query.filter(DefaultCredentialEntry.service == service)
    entries = query.order_by(
        DefaultCredentialEntry.service, DefaultCredentialEntry.vendor
    ).all()
    return [_serialize_credential_list(e) for e in entries]


_PROBE_METHODS = {"GET", "POST"}
_PROBE_ENCODINGS = {"form", "json"}


def _validate_credential_list(body: CredentialListIn) -> dict[str, str]:
    errors: dict[str, str] = {}
    if body.service not in ALLOWED_SERVICES:
        errors["service"] = f"service must be one of {sorted(ALLOWED_SERVICES)}"
    if not body.vendor.strip():
        errors["vendor"] = "vendor is required."
    for cred in body.credentials:
        if not cred.username or not cred.secret:
            errors["credentials"] = "each credential needs a username and a secret."
            break
    # probe_config is optional; when present it must be an object with a valid
    # method/encoding (feature 008). Unknown keys are ignored by the probe.
    cfg = body.probe_config
    if cfg:
        if not isinstance(cfg, dict):
            errors["probe_config"] = "probe_config must be an object."
        else:
            method = cfg.get("method")
            if method is not None and str(method).upper() not in _PROBE_METHODS:
                errors["probe_config"] = f"method must be one of {sorted(_PROBE_METHODS)}"
            encoding = cfg.get("encoding")
            if encoding is not None and encoding not in _PROBE_ENCODINGS:
                errors["probe_config"] = f"encoding must be one of {sorted(_PROBE_ENCODINGS)}"
    return errors


@router.post("/credentials", status_code=201)
def api_create_credential_list(
    body: CredentialListIn,
    session: Session = Depends(get_session),
    account: OperatorAccount = Depends(require_operator),
):
    errors = _validate_credential_list(body)
    if errors:
        return validation_error(errors)

    entry = DefaultCredentialEntry(
        vendor=body.vendor.strip(),
        service=body.service,
        credentials=[c.model_dump() for c in body.credentials],
        success_keywords=body.success_keywords,
        probe_config=body.probe_config,
    )
    session.add(entry)
    session.flush()
    record_event(
        session,
        AuditEventType.CONFIG_CHANGE,
        actor_id=account.id,
        detail={
            "action": "create_credential_list",
            "entry_id": entry.id,
            "service": entry.service,
            "vendor": entry.vendor,
            "pair_count": len(entry.credentials),
        },
    )
    session.commit()
    return _serialize_credential_list(entry)


@router.put("/credentials/{entry_id}")
def api_update_credential_list(
    entry_id: str,
    body: CredentialListIn,
    session: Session = Depends(get_session),
    account: OperatorAccount = Depends(require_operator),
):
    entry = session.get(DefaultCredentialEntry, entry_id)
    if entry is None:
        return JSONResponse(status_code=404, content=api_error("not_found", "Entry not found."))

    errors = _validate_credential_list(body)
    if errors:
        return validation_error(errors)

    entry.vendor = body.vendor.strip()
    entry.service = body.service
    entry.credentials = [c.model_dump() for c in body.credentials]
    entry.success_keywords = body.success_keywords
    entry.probe_config = body.probe_config
    session.add(entry)
    record_event(
        session,
        AuditEventType.CONFIG_CHANGE,
        actor_id=account.id,
        detail={
            "action": "update_credential_list",
            "entry_id": entry.id,
            "service": entry.service,
            "vendor": entry.vendor,
            "pair_count": len(entry.credentials),
        },
    )
    session.commit()
    return _serialize_credential_list(entry)


@router.delete("/credentials/{entry_id}", status_code=204)
def api_delete_credential_list(
    entry_id: str,
    session: Session = Depends(get_session),
    account: OperatorAccount = Depends(require_operator),
):
    entry = session.get(DefaultCredentialEntry, entry_id)
    if entry is None:
        return JSONResponse(status_code=404, content=api_error("not_found", "Entry not found."))
    detail = {
        "action": "delete_credential_list",
        "entry_id": entry.id,
        "service": entry.service,
        "vendor": entry.vendor,
    }
    session.delete(entry)
    record_event(session, AuditEventType.CONFIG_CHANGE, actor_id=account.id, detail=detail)
    session.commit()
    return Response(status_code=204)


@pages_router.get("/tools/credential-check")
def credential_tool_page(request: Request, session: Session = Depends(get_session)):
    return templates.TemplateResponse(
        request, "credential_tool.html", {**session_context(request, session)}
    )


@pages_router.get("/tools/credential-check/runs/{run_id}")
def credential_tool_run_detail_page(
    run_id: str, request: Request, session: Session = Depends(get_session)
):
    """Scan-style per-attempt result page (US6, 3.5). Server-rendered like the
    discovery run_detail.html; polls while the run is still `running`."""
    run = session.get(ToolCheckRun, run_id)
    if run is None:
        return templates.TemplateResponse(
            request,
            "tool_run_detail.html",
            {**session_context(request, session), "run": None, "results": []},
            status_code=404,
        )
    return templates.TemplateResponse(
        request,
        "tool_run_detail.html",
        {
            **session_context(request, session),
            "run": _serialize_run(run),
            "results": _serialize_run_detail(run)["results"],
        },
    )

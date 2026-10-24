"""Discovery run routes (FR-016-FR-021, FR-024, FR-025, FR-043). See contracts/http-api.md."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from asset_dashboard.auth.authz import session_context
from asset_dashboard.db.base import get_session
from asset_dashboard.db.models import DiscoveryRun, OperatorAccount, RunTrigger
from asset_dashboard.discovery.runner import (
    AlreadyRunningError,
    ConcurrencyLimitError,
    cancel_run,
    start_adhoc_run,
    start_run,
)
from asset_dashboard.history.cache import find_fresh_run, serve_from_cache
from asset_dashboard.nse.allowlist import enabled_script_ids
from asset_dashboard.profiles.service import ProfileNotFoundError, get_profile
from asset_dashboard.profiles.validation import (
    validate_extracted_fields,
    validate_port_spec,
    validate_profile,
    validate_scan_params,
    validate_selected_scripts,
    validate_target_scope,
)
from asset_dashboard.web.errors import api_error, validation_error
from asset_dashboard.web.templating import templates

router = APIRouter(prefix="/api")
pages_router = APIRouter()


class StartRunRequest(BaseModel):
    force_fresh: bool = False
    target_scope: list[str] | None = None
    # Feature 009: optional one-off per-run overrides from the Scan
    # Configuration page. All default None (backward compatible); when
    # present each is validated by the matching profiles/validation.py
    # allow-list validator and written only into the run's snapshot — the
    # saved profile is never mutated (FR-017).
    port_spec: str | None = None
    scan_params: dict | None = None
    extracted_fields: list[str] | None = None
    selected_scripts: list[str] | None = None
    compliance_settings: dict | None = None


class AdHocRunRequest(BaseModel):
    """Feature 009 (course-corrected): a fully editable one-off scan that runs
    WITHOUT persisting a profile. Same fields as a profile, all validated by
    the same allow-list validators; `name` is optional (labels the run only)."""

    name: str | None = None
    target_scope: list[str] = []
    port_spec: str = ""
    scan_params: dict = {}
    extracted_fields: list[str] = []
    selected_scripts: list[str] = []
    compliance_settings: dict = {}


def _serialize_run(run: DiscoveryRun) -> dict:
    return {
        "id": run.id,
        "profile_id": run.profile_id,
        "profile_snapshot": run.profile_snapshot,
        "trigger": run.trigger.value,
        "status": run.status.value,
        "served_from_cache": run.served_from_cache,
        "source_run_id": run.source_run_id,
        "started_at": run.started_at.isoformat(),
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "params_used": run.params_used,
        "summary": run.summary,
        "error_detail": run.error_detail,
    }


def _serialize_results(run: DiscoveryRun) -> list[dict]:
    return [
        {
            "address": asset.address,
            "state": asset.state.value,
            "open_ports": asset.open_ports,
            "extracted": asset.extracted,
            "management_link": asset.management_link,
            "findings": [
                {"control": f.control.value, "result": f.result.value, "detail": f.detail}
                for f in asset.findings
            ],
        }
        for asset in run.assets
    ]


@router.post("/profiles/{profile_id}/runs", status_code=202)
def api_start_run(
    profile_id: str,
    body: StartRunRequest,
    request: Request,
    session: Session = Depends(get_session),
):
    try:
        profile = get_profile(session, profile_id)
    except ProfileNotFoundError:
        return JSONResponse(status_code=404, content=api_error("not_found", "Profile not found."))

    username = getattr(request.state, "user", None)
    actor_id = None
    if username:
        account = session.query(OperatorAccount).filter_by(username=username).one_or_none()
        actor_id = account.id if account else None

    target_override = body.target_scope
    if target_override is not None:
        target_error = validate_target_scope(target_override)
        if target_error:
            return validation_error({"target_scope": target_error})

    # Feature 009: validate each present one-off override with the same
    # allow-list validators the profile editor uses — no raw nmap flag can
    # reach the command line (FR-018).
    if body.port_spec is not None:
        port_error = validate_port_spec(body.port_spec)
        if port_error:
            return validation_error({"port_spec": port_error})
    if body.scan_params is not None:
        scan_params_error = validate_scan_params(body.scan_params)
        if scan_params_error:
            return validation_error({"scan_params": scan_params_error})
    if body.extracted_fields is not None:
        fields_error = validate_extracted_fields(body.extracted_fields)
        if fields_error:
            return validation_error({"extracted_fields": fields_error})
    if body.selected_scripts is not None:
        scripts_error = validate_selected_scripts(
            body.selected_scripts, enabled_script_ids(session)
        )
        if scripts_error:
            return validation_error({"selected_scripts": scripts_error})

    effective_target = target_override if target_override is not None else profile.target_scope
    if not effective_target:
        return JSONResponse(
            status_code=400,
            content=api_error("target_required", "A target is required to start this run."),
        )

    # Any present override makes the launch fresh; cache is served only when
    # the effective run is unchanged from the saved profile (R2).
    has_override = (
        target_override is not None
        or body.port_spec is not None
        or body.scan_params is not None
        or body.extracted_fields is not None
        or body.selected_scripts is not None
        or body.compliance_settings is not None
    )
    if not body.force_fresh and not has_override:
        fresh = find_fresh_run(session, profile)
        if fresh is not None:
            cached_run = serve_from_cache(
                session, profile, fresh, trigger=RunTrigger.MANUAL, triggered_by_id=actor_id
            )
            session.commit()
            return JSONResponse(
                status_code=200,
                content={
                    "run_id": cached_run.id,
                    "status": cached_run.status.value,
                    "served_from_cache": True,
                    "source_run_id": cached_run.source_run_id,
                },
            )

    try:
        run = start_run(
            session,
            profile,
            trigger=RunTrigger.MANUAL,
            triggered_by_id=actor_id,
            target_override=target_override,
            port_spec_override=body.port_spec,
            scan_params_override=body.scan_params,
            extracted_fields_override=body.extracted_fields,
            selected_scripts_override=body.selected_scripts,
            compliance_settings_override=body.compliance_settings,
        )
    except AlreadyRunningError:
        return JSONResponse(
            status_code=409,
            content=api_error("already_running", "A run of this profile is already in progress."),
        )
    except ConcurrencyLimitError:
        return JSONResponse(
            status_code=503,
            content=api_error("concurrency_limit", "Too many concurrent runs. Try again shortly."),
        )

    return JSONResponse(status_code=202, content={"run_id": run.id, "status": run.status.value})


ADHOC_RUN_DEFAULT_NAME = "Довільне сканування"


@router.post("/runs/ad-hoc", status_code=202)
def api_start_adhoc_run(
    body: AdHocRunRequest,
    request: Request,
    session: Session = Depends(get_session),
):
    """Launch a one-off scan from a fully editable configuration without saving
    a profile. All fields are validated with the same allow-list validators as
    the profile editor (NSE scripts checked against the enabled allow-list), so
    no raw nmap flag can be injected (FR-018)."""
    name = (body.name or "").strip() or ADHOC_RUN_DEFAULT_NAME
    scan_params = dict(body.scan_params)
    scan_params.setdefault("timing", "T3")

    payload = {
        "name": name,
        "target_scope": body.target_scope,
        "port_spec": body.port_spec,
        "scan_params": scan_params,
        "extracted_fields": body.extracted_fields,
        "selected_scripts": body.selected_scripts,
    }
    errors = validate_profile(
        payload, allowlisted_script_ids=enabled_script_ids(session), require_target=True
    )
    if errors:
        return validation_error(errors)

    username = getattr(request.state, "user", None)
    actor_id = None
    if username:
        account = session.query(OperatorAccount).filter_by(username=username).one_or_none()
        actor_id = account.id if account else None

    try:
        run = start_adhoc_run(
            session,
            name=name,
            target_scope=body.target_scope,
            port_spec=body.port_spec,
            scan_params=scan_params,
            extracted_fields=body.extracted_fields,
            selected_scripts=body.selected_scripts,
            compliance_settings=body.compliance_settings,
            trigger=RunTrigger.MANUAL,
            triggered_by_id=actor_id,
        )
    except ConcurrencyLimitError:
        return JSONResponse(
            status_code=503,
            content=api_error("concurrency_limit", "Too many concurrent runs. Try again shortly."),
        )

    return JSONResponse(status_code=202, content={"run_id": run.id, "status": run.status.value})


@router.get("/runs/{run_id}")
def api_get_run(run_id: str, session: Session = Depends(get_session)):
    run = session.get(DiscoveryRun, run_id)
    if run is None:
        return JSONResponse(status_code=404, content=api_error("not_found", "Run not found."))
    return _serialize_run(run)


@router.post("/runs/{run_id}/cancel")
def api_cancel_run(run_id: str, session: Session = Depends(get_session)):
    run = session.get(DiscoveryRun, run_id)
    if run is None:
        return JSONResponse(status_code=404, content=api_error("not_found", "Run not found."))
    cancel_run(run_id)
    return {"ok": True}


@router.get("/runs/{run_id}/results")
def api_get_run_results(run_id: str, session: Session = Depends(get_session)):
    run = session.get(DiscoveryRun, run_id)
    if run is None:
        return JSONResponse(status_code=404, content=api_error("not_found", "Run not found."))
    return _serialize_results(run)


@pages_router.get("/runs/{run_id}")
def run_detail_page(run_id: str, request: Request, session: Session = Depends(get_session)):
    run = session.get(DiscoveryRun, run_id)
    if run is None:
        return JSONResponse(status_code=404, content=api_error("not_found", "Run not found."))
    return templates.TemplateResponse(
        request,
        "run_detail.html",
        {
            "run": _serialize_run(run),
            "results": _serialize_results(run),
            **session_context(request, session),
        },
    )

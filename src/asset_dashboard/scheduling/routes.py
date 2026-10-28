"""Schedule routes (FR-020-FR-023, FR-028-FR-032). See contracts/http-api-delta.md.

Feature 003 (US6): a profile may now have multiple schedules, each
carrying its own `target_scope` (so target-less profiles are schedulable)
and an optional `label`. Routes moved from the single-schedule-per-profile
shape (`/api/profiles/{id}/schedule`) to per-schedule CRUD
(`/api/profiles/{id}/schedules`, `/api/schedules/{schedule_id}`), plus a
create-from-history endpoint.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from asset_dashboard.archival import archive_oldest
from asset_dashboard.audit.log import record_event
from asset_dashboard.auth.authz import session_context
from asset_dashboard.db.base import get_session
from asset_dashboard.db.models import (
    AuditEventType,
    CatchUpPolicy,
    DiscoveryProfile,
    DiscoveryRun,
    OverlapPolicy,
    Schedule,
    utcnow,
)
from asset_dashboard.profiles.validation import validate_target_scope
from asset_dashboard.scheduling.engine import compute_next_run_at, validate_recurrence
from asset_dashboard.web.errors import api_error, validation_error
from asset_dashboard.web.templating import templates

router = APIRouter(prefix="/api")
pages_router = APIRouter()


class ScheduleIn(BaseModel):
    recurrence: dict
    target_scope: list[str] | None = None
    label: str | None = None
    enabled: bool = True
    overlap_policy: OverlapPolicy = OverlapPolicy.SKIP
    catch_up_policy: CatchUpPolicy = CatchUpPolicy.RUN_ONCE


class ScheduleFromRunIn(BaseModel):
    recurrence: dict
    label: str | None = None
    enabled: bool = True
    overlap_policy: OverlapPolicy = OverlapPolicy.SKIP
    catch_up_policy: CatchUpPolicy = CatchUpPolicy.RUN_ONCE


def _serialize(schedule: Schedule) -> dict:
    return {
        "id": schedule.id,
        "profile_id": schedule.profile_id,
        "recurrence": schedule.recurrence,
        "target_scope": schedule.target_scope,
        "label": schedule.label,
        "enabled": schedule.enabled,
        "next_run_at": schedule.next_run_at.isoformat(),
        "overlap_policy": schedule.overlap_policy.value,
        "catch_up_policy": schedule.catch_up_policy.value,
        "last_triggered_at": schedule.last_triggered_at.isoformat()
        if schedule.last_triggered_at
        else None,
    }


@router.get("/profiles/{profile_id}/schedules")
def api_list_schedules(profile_id: str, session: Session = Depends(get_session)):
    profile = session.get(DiscoveryProfile, profile_id)
    if profile is None:
        return JSONResponse(status_code=404, content=api_error("not_found", "Profile not found."))
    schedules = session.query(Schedule).filter_by(profile_id=profile_id).all()
    return [_serialize(s) for s in schedules]


@router.post("/profiles/{profile_id}/schedules", status_code=201)
def api_create_schedule(profile_id: str, body: ScheduleIn, session: Session = Depends(get_session)):
    profile = session.get(DiscoveryProfile, profile_id)
    if profile is None:
        return JSONResponse(status_code=404, content=api_error("not_found", "Profile not found."))

    now = utcnow()
    try:
        validate_recurrence(body.recurrence, now=now)
        next_run_at = compute_next_run_at(body.recurrence, now)
    except Exception as exc:  # noqa: BLE001 - surfaced to the caller as a validation error
        return validation_error({"recurrence": str(exc)})

    target_scope = (
        body.target_scope if body.target_scope is not None else list(profile.target_scope)
    )
    target_error = validate_target_scope(target_scope)
    if target_error:
        return validation_error({"target_scope": target_error})

    schedule = Schedule(
        profile_id=profile_id,
        recurrence=body.recurrence,
        target_scope=target_scope,
        label=body.label,
        enabled=body.enabled,
        overlap_policy=body.overlap_policy,
        catch_up_policy=body.catch_up_policy,
        next_run_at=next_run_at,
    )
    session.add(schedule)
    session.flush()

    record_event(
        session,
        AuditEventType.SCHEDULE_CHANGE,
        detail={"profile_id": profile_id, "schedule_id": schedule.id, "action": "create"},
    )
    archive_oldest(session, Schedule, Schedule.created_at)
    session.commit()
    return _serialize(schedule)


@router.put("/schedules/{schedule_id}")
def api_update_schedule(
    schedule_id: str, body: ScheduleIn, session: Session = Depends(get_session)
):
    schedule = session.get(Schedule, schedule_id)
    if schedule is None:
        return JSONResponse(status_code=404, content=api_error("not_found", "Schedule not found."))

    now = utcnow()
    try:
        validate_recurrence(body.recurrence, now=now)
        next_run_at = compute_next_run_at(body.recurrence, now)
    except Exception as exc:  # noqa: BLE001
        return validation_error({"recurrence": str(exc)})

    target_scope = body.target_scope if body.target_scope is not None else schedule.target_scope
    target_error = validate_target_scope(target_scope)
    if target_error:
        return validation_error({"target_scope": target_error})

    schedule.recurrence = body.recurrence
    schedule.target_scope = target_scope
    schedule.label = body.label
    schedule.enabled = body.enabled
    schedule.overlap_policy = body.overlap_policy
    schedule.catch_up_policy = body.catch_up_policy
    schedule.next_run_at = next_run_at

    record_event(
        session,
        AuditEventType.SCHEDULE_CHANGE,
        detail={"profile_id": schedule.profile_id, "schedule_id": schedule.id, "action": "update"},
    )
    session.commit()
    return _serialize(schedule)


@router.delete("/schedules/{schedule_id}", status_code=204)
def api_delete_schedule(schedule_id: str, session: Session = Depends(get_session)):
    schedule = session.get(Schedule, schedule_id)
    if schedule is None:
        return JSONResponse(status_code=404, content=api_error("not_found", "Schedule not found."))

    profile_id = schedule.profile_id
    session.delete(schedule)
    record_event(
        session,
        AuditEventType.SCHEDULE_CHANGE,
        detail={"profile_id": profile_id, "schedule_id": schedule_id, "action": "delete"},
    )
    session.commit()
    return Response(status_code=204)


@router.post("/runs/{run_id}/schedule", status_code=201)
def api_schedule_from_run(
    run_id: str, body: ScheduleFromRunIn, session: Session = Depends(get_session)
):
    run = session.get(DiscoveryRun, run_id)
    if run is None:
        return JSONResponse(status_code=404, content=api_error("not_found", "Run not found."))

    profile = session.get(DiscoveryProfile, run.profile_id) if run.profile_id else None
    if profile is None:
        return JSONResponse(
            status_code=404, content=api_error("not_found", "The run's profile no longer exists.")
        )

    now = utcnow()
    try:
        validate_recurrence(body.recurrence, now=now)
        next_run_at = compute_next_run_at(body.recurrence, now)
    except Exception as exc:  # noqa: BLE001
        return validation_error({"recurrence": str(exc)})

    target_scope = list((run.params_used or {}).get("target_scope") or [])
    target_error = validate_target_scope(target_scope)
    if target_error:
        return validation_error({"target_scope": target_error})

    schedule = Schedule(
        profile_id=profile.id,
        recurrence=body.recurrence,
        target_scope=target_scope,
        label=body.label,
        enabled=body.enabled,
        overlap_policy=body.overlap_policy,
        catch_up_policy=body.catch_up_policy,
        next_run_at=next_run_at,
    )
    session.add(schedule)
    session.flush()

    record_event(
        session,
        AuditEventType.SCHEDULE_CHANGE,
        detail={
            "profile_id": profile.id,
            "schedule_id": schedule.id,
            "action": "create_from_run",
            "source_run_id": run_id,
        },
    )
    archive_oldest(session, Schedule, Schedule.created_at)
    session.commit()
    return _serialize(schedule)


@pages_router.get("/schedules")
def schedules_page(
    request: Request,
    from_run: str | None = None,
    include_archived: bool = False,
    session: Session = Depends(get_session),
):
    query = session.query(Schedule)
    if not include_archived:
        query = query.filter(Schedule.archived.is_(False))
    schedules = query.all()
    rows = []
    for s in schedules:
        profile = session.get(DiscoveryProfile, s.profile_id)
        rows.append({**_serialize(s), "profile_name": profile.name if profile else "(deleted)"})
    profiles = session.query(DiscoveryProfile).order_by(DiscoveryProfile.name).all()

    # "Schedule this scan" (from Home / History / a run's results) links here with
    # ?from_run=<id>. Pre-fill the create form with that run's profile and the
    # exact target it scanned, so the operator only has to pick a recurrence
    # (profile/target remain editable). An unknown run or a deleted profile
    # simply yields no prefill rather than an error.
    prefill = None
    if from_run:
        run = session.get(DiscoveryRun, from_run)
        if run is not None and run.profile_id and session.get(DiscoveryProfile, run.profile_id):
            target_scope = list((run.params_used or {}).get("target_scope") or [])
            prefill = {
                "profile_id": run.profile_id,
                "target_scope": ", ".join(target_scope),
            }

    return templates.TemplateResponse(
        request,
        "schedules.html",
        {
            "schedules": rows,
            "profiles": [{"id": p.id, "name": p.name} for p in profiles],
            "prefill": prefill,
            "include_archived": include_archived,
            **session_context(request, session),
        },
    )

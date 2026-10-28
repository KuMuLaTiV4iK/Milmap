"""History routes (FR-022, FR-023). See contracts/http-api.md."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from asset_dashboard.auth.authz import session_context
from asset_dashboard.db.base import get_session
from asset_dashboard.db.models import DiscoveryRun
from asset_dashboard.discovery.routes import _serialize_results, _serialize_run
from asset_dashboard.history.service import list_runs
from asset_dashboard.web.errors import api_error
from asset_dashboard.web.templating import templates

router = APIRouter(prefix="/api/history")
pages_router = APIRouter()


def _serialize_summary(run: DiscoveryRun) -> dict:
    return {
        "id": run.id,
        "profile_name": run.profile_snapshot.get("name"),
        "params_used": run.params_used,
        "status": run.status.value,
        "started_at": run.started_at.isoformat(),
        "served_from_cache": run.served_from_cache,
        "summary": run.summary,
    }


@router.get("")
def api_list_history(
    profile_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    include_archived: bool = False,
    session: Session = Depends(get_session),
):
    runs = list_runs(
        session,
        profile_id=profile_id,
        status=status,
        limit=limit,
        offset=offset,
        include_archived=include_archived,
    )
    return [_serialize_summary(r) for r in runs]


@router.get("/{run_id}")
def api_get_history_run(run_id: str, session: Session = Depends(get_session)):
    run = session.get(DiscoveryRun, run_id)
    if run is None:
        return JSONResponse(status_code=404, content=api_error("not_found", "Run not found."))
    return {"run": _serialize_run(run), "results": _serialize_results(run)}


@pages_router.get("/history")
def history_page(
    request: Request, include_archived: bool = False, session: Session = Depends(get_session)
):
    runs = list_runs(session, limit=100, include_archived=include_archived)
    return templates.TemplateResponse(
        request,
        "history.html",
        {
            "runs": [_serialize_summary(r) for r in runs],
            "include_archived": include_archived,
            **session_context(request, session),
        },
    )

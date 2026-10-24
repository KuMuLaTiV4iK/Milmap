"""Reference-versions routes (FR-015, FR-015a, FR-015b). See
contracts/http-api-delta.md. Session-authenticated, Operators AND
Administrators (not admin-gated); every mutation is audit-logged."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, RedirectResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from asset_dashboard.audit.log import record_event
from asset_dashboard.auth.authz import require_operator
from asset_dashboard.db.base import get_session
from asset_dashboard.db.models import AuditEventType, OperatorAccount, ReferenceVersionEntry
from asset_dashboard.reference_versions.service import (
    ReferenceVersionNotFoundError,
    create_entry,
    delete_entry,
    list_entries,
    update_entry,
    validate_reference_version,
)
from asset_dashboard.web.errors import api_error, validation_error

router = APIRouter(prefix="/api/reference-versions")
pages_router = APIRouter()


class ReferenceVersionIn(BaseModel):
    vendor: str
    type: str
    model: str | None = None
    min_version: str
    note: str | None = None


def _serialize(entry: ReferenceVersionEntry) -> dict:
    return {
        "id": entry.id,
        "vendor": entry.vendor,
        "type": entry.type,
        "model": entry.model,
        "min_version": entry.min_version,
        "note": entry.note,
        "source": entry.source,
        "needs_review": entry.needs_review,
        "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
    }


@router.get("")
def api_list_reference_versions(
    session: Session = Depends(get_session),
    _account: OperatorAccount = Depends(require_operator),
):
    return [_serialize(e) for e in list_entries(session)]


@router.post("", status_code=201)
def api_create_reference_version(
    body: ReferenceVersionIn,
    session: Session = Depends(get_session),
    account: OperatorAccount = Depends(require_operator),
):
    payload = body.model_dump()
    error = validate_reference_version(payload)
    if error:
        return validation_error({"detail": error})

    entry = create_entry(session, payload)
    record_event(
        session,
        AuditEventType.CONFIG_CHANGE,
        actor_id=account.id,
        detail={"action": "create", "entry_id": entry.id, "vendor": entry.vendor},
    )
    session.commit()
    return _serialize(entry)


@router.put("/{entry_id}")
def api_update_reference_version(
    entry_id: str,
    body: ReferenceVersionIn,
    session: Session = Depends(get_session),
    account: OperatorAccount = Depends(require_operator),
):
    payload = body.model_dump()
    error = validate_reference_version(payload)
    if error:
        return validation_error({"detail": error})

    try:
        entry = update_entry(session, entry_id, payload)
    except ReferenceVersionNotFoundError:
        return JSONResponse(status_code=404, content=api_error("not_found", "Entry not found."))

    record_event(
        session,
        AuditEventType.CONFIG_CHANGE,
        actor_id=account.id,
        detail={"action": "update", "entry_id": entry.id, "vendor": entry.vendor},
    )
    session.commit()
    return _serialize(entry)


@router.delete("/{entry_id}", status_code=204)
def api_delete_reference_version(
    entry_id: str,
    session: Session = Depends(get_session),
    account: OperatorAccount = Depends(require_operator),
):
    try:
        delete_entry(session, entry_id)
    except ReferenceVersionNotFoundError:
        return JSONResponse(status_code=404, content=api_error("not_found", "Entry not found."))

    record_event(
        session,
        AuditEventType.CONFIG_CHANGE,
        actor_id=account.id,
        detail={"action": "delete", "entry_id": entry_id},
    )
    session.commit()
    return Response(status_code=204)


@pages_router.get("/reference-versions")
def reference_versions_page():
    """Feature 006 (FR-013a): the version dictionary now lives inside the
    Configuration page. Redirect the old standalone URL so existing
    bookmarks are not stranded."""
    return RedirectResponse(url="/configuration", status_code=307)

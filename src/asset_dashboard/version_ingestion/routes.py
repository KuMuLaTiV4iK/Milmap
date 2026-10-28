"""Version-ingestion routes (FR-014, FR-016-FR-021; contracts/http-api-delta.md
§B/§C). Admin-only: tracked-source CRUD and bundle import preview/apply —
the higher trust of cross-boundary data (Constitution Principle VII)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from asset_dashboard.audit.log import record_event
from asset_dashboard.auth.authz import require_admin
from asset_dashboard.config import load_version_ingestion_keys
from asset_dashboard.db.base import get_session
from asset_dashboard.db.models import AuditEventType, OperatorAccount, VersionIngestionSource
from asset_dashboard.version_ingestion.bundle import BundleInvalidError
from asset_dashboard.version_ingestion.service import (
    SourceNotFoundError,
    apply_import,
    create_source,
    delete_source,
    list_sources,
    preview_import,
    update_source,
    validate_source,
)
from asset_dashboard.web.errors import api_error, validation_error

router = APIRouter(prefix="/api/version-ingestion")


class SourceIn(BaseModel):
    vendor: str
    source_url: str
    models: list[str]
    extractor: dict | None = None


def _serialize_source(source: VersionIngestionSource) -> dict:
    return {
        "id": source.id,
        "vendor": source.vendor,
        "source_url": source.source_url,
        "models": source.models,
        "last_import_status": source.last_import_status,
        "last_import_at": source.last_import_at.isoformat() if source.last_import_at else None,
        "last_versions": source.last_versions,
    }


@router.get("/sources")
def api_list_sources(
    session: Session = Depends(get_session),
    _account: OperatorAccount = Depends(require_admin),
):
    return [_serialize_source(s) for s in list_sources(session)]


@router.post("/sources", status_code=201)
def api_create_source(
    body: SourceIn,
    session: Session = Depends(get_session),
    account: OperatorAccount = Depends(require_admin),
):
    payload = body.model_dump()
    error = validate_source(payload)
    if error:
        return validation_error({"detail": error})

    source = create_source(session, payload, created_by=account.id)
    record_event(
        session,
        AuditEventType.CONFIG_CHANGE,
        actor_id=account.id,
        detail={"action": "create_source", "vendor": source.vendor},
    )
    session.commit()
    return _serialize_source(source)


@router.put("/sources/{source_id}")
def api_update_source(
    source_id: str,
    body: SourceIn,
    session: Session = Depends(get_session),
    account: OperatorAccount = Depends(require_admin),
):
    payload = body.model_dump()
    error = validate_source(payload)
    if error:
        return validation_error({"detail": error})

    try:
        source = update_source(session, source_id, payload)
    except SourceNotFoundError:
        return JSONResponse(status_code=404, content=api_error("not_found", "Source not found."))

    record_event(
        session,
        AuditEventType.CONFIG_CHANGE,
        actor_id=account.id,
        detail={"action": "update_source", "vendor": source.vendor},
    )
    session.commit()
    return _serialize_source(source)


@router.delete("/sources/{source_id}", status_code=204)
def api_delete_source(
    source_id: str,
    session: Session = Depends(get_session),
    account: OperatorAccount = Depends(require_admin),
):
    try:
        delete_source(session, source_id)
    except SourceNotFoundError:
        return JSONResponse(status_code=404, content=api_error("not_found", "Source not found."))

    record_event(
        session,
        AuditEventType.CONFIG_CHANGE,
        actor_id=account.id,
        detail={"action": "delete_source", "source_id": source_id},
    )
    session.commit()
    return Response(status_code=204)


class ImportPreviewIn(BaseModel):
    bundle: dict


class ImportApplyIn(BaseModel):
    bundle: dict
    source_id: str | None = None
    confirm_downgrade: bool = False


@router.post("/import/preview")
def api_import_preview(
    body: ImportPreviewIn,
    session: Session = Depends(get_session),
    _account: OperatorAccount = Depends(require_admin),
):
    import json

    keys = load_version_ingestion_keys()
    try:
        review = preview_import(session, json.dumps(body.bundle), keys)
    except BundleInvalidError as exc:
        return JSONResponse(status_code=400, content=api_error("bundle_invalid", str(exc)))
    return review


@router.post("/import/apply")
def api_import_apply(
    body: ImportApplyIn,
    session: Session = Depends(get_session),
    account: OperatorAccount = Depends(require_admin),
):
    import json

    keys = load_version_ingestion_keys()
    try:
        result = apply_import(
            session,
            json.dumps(body.bundle),
            keys,
            source_id=body.source_id,
            confirm_downgrade=body.confirm_downgrade,
        )
    except BundleInvalidError as exc:
        return JSONResponse(status_code=400, content=api_error("bundle_invalid", str(exc)))

    record_event(
        session,
        AuditEventType.CONFIG_CHANGE,
        actor_id=account.id,
        detail={"action": "import", "source_id": body.source_id, **result},
    )
    session.commit()
    return result

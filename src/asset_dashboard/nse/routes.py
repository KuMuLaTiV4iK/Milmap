"""NSE allow-list routes (FR-010-FR-018). See contracts/http-api-delta.md."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from asset_dashboard.audit.log import record_event
from asset_dashboard.auth.authz import require_admin, require_operator
from asset_dashboard.db.base import get_session
from asset_dashboard.db.models import AuditEventType, NseScriptAllowlistEntry, OperatorAccount
from asset_dashboard.nse.allowlist import (
    DuplicateScriptIdError,
    InvalidScriptIdError,
    NmapScriptsNotFoundError,
    create_entry,
    delete_entry,
    import_from_nmap_scripts,
    list_entries,
    update_entry,
)
from asset_dashboard.web.errors import api_error, validation_error

router = APIRouter(prefix="/api/nse-scripts")


class NseScriptIn(BaseModel):
    script_id: str
    description: str | None = None
    safety: str = "safe"
    expected_ports: list[int] = Field(default_factory=list)


class NseScriptUpdateIn(BaseModel):
    description: str | None = None
    safety: str | None = None
    expected_ports: list[int] | None = None
    enabled: bool | None = None


def _serialize(entry: NseScriptAllowlistEntry) -> dict:
    return {
        "id": entry.id,
        "script_id": entry.script_id,
        "description": entry.description,
        "safety": entry.safety,
        "expected_ports": entry.expected_ports,
        "enabled": entry.enabled,
    }


@router.get("")
def api_list_nse_scripts(
    session: Session = Depends(get_session),
    _account: OperatorAccount = Depends(require_operator),
):
    return [_serialize(e) for e in list_entries(session)]


@router.post("", status_code=201)
def api_create_nse_script(
    body: NseScriptIn,
    session: Session = Depends(get_session),
    account: OperatorAccount = Depends(require_admin),
):
    try:
        entry = create_entry(
            session,
            script_id=body.script_id,
            description=body.description,
            safety=body.safety,
            expected_ports=body.expected_ports,
            created_by=account.id,
        )
    except InvalidScriptIdError as exc:
        return validation_error({"script_id": str(exc)})
    except DuplicateScriptIdError as exc:
        return validation_error({"script_id": str(exc)})

    record_event(
        session,
        AuditEventType.ALLOWLIST_CHANGE,
        actor_id=account.id,
        detail={"action": "create", "script_id": entry.script_id, "safety": entry.safety},
    )
    session.commit()

    result = _serialize(entry)
    if entry.safety != "safe":
        result["warning"] = "non_safe_script"
    return result


@router.post("/import")
def api_import_nse_scripts(
    session: Session = Depends(get_session),
    account: OperatorAccount = Depends(require_admin),
):
    """Bulk-add every script in the local nmap install's catalog
    (FR-016) — offline, reads `scripts/script.db` next to the local
    `nmap` binary; never a network fetch."""
    try:
        result = import_from_nmap_scripts(session, created_by=account.id)
    except NmapScriptsNotFoundError as exc:
        return JSONResponse(status_code=400, content=api_error("nmap_scripts_not_found", str(exc)))

    record_event(
        session,
        AuditEventType.ALLOWLIST_CHANGE,
        actor_id=account.id,
        detail={"action": "bulk_import", **result},
    )
    session.commit()
    return result


@router.put("/{entry_id}")
def api_update_nse_script(
    entry_id: str,
    body: NseScriptUpdateIn,
    session: Session = Depends(get_session),
    account: OperatorAccount = Depends(require_admin),
):
    entry = update_entry(
        session,
        entry_id,
        description=body.description,
        safety=body.safety,
        expected_ports=body.expected_ports,
        enabled=body.enabled,
    )
    if entry is None:
        return JSONResponse(status_code=404, content=api_error("not_found", "Script not found."))

    record_event(
        session,
        AuditEventType.ALLOWLIST_CHANGE,
        actor_id=account.id,
        detail={"action": "update", "script_id": entry.script_id},
    )
    session.commit()

    result = _serialize(entry)
    if entry.safety != "safe":
        result["warning"] = "non_safe_script"
    return result


@router.delete("/{entry_id}", status_code=204)
def api_delete_nse_script(
    entry_id: str,
    session: Session = Depends(get_session),
    account: OperatorAccount = Depends(require_admin),
):
    entry = session.get(NseScriptAllowlistEntry, entry_id)
    if entry is None:
        return JSONResponse(status_code=404, content=api_error("not_found", "Script not found."))
    script_id = entry.script_id
    delete_entry(session, entry_id)

    record_event(
        session,
        AuditEventType.ALLOWLIST_CHANGE,
        actor_id=account.id,
        detail={"action": "delete", "script_id": script_id},
    )
    session.commit()
    return Response(status_code=204)

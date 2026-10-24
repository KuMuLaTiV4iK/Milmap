"""Security-settings routes + the Configuration page (FR-032). See contracts/http-api-delta.md."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from asset_dashboard.audit.log import record_event
from asset_dashboard.auth.authz import require_admin, session_context
from asset_dashboard.db.base import get_session
from asset_dashboard.db.models import AuditEventType, OperatorAccount
from asset_dashboard.settings_store.service import (
    SettingsValidationError,
    get_effective_settings,
    update_settings,
)
from asset_dashboard.web.errors import validation_error
from asset_dashboard.web.templating import templates

router = APIRouter(prefix="/api/settings/security")
pages_router = APIRouter()


@pages_router.get("/configuration")
def configuration_page(request: Request, session: Session = Depends(get_session)):
    return templates.TemplateResponse(
        request, "configuration.html", {**session_context(request, session)}
    )


@router.get("")
def api_get_security_settings(
    session: Session = Depends(get_session),
    _account: OperatorAccount = Depends(require_admin),
):
    return get_effective_settings(session)


@router.put("")
def api_put_security_settings(
    body: dict,
    session: Session = Depends(get_session),
    account: OperatorAccount = Depends(require_admin),
):
    try:
        result = update_settings(session, body)
    except SettingsValidationError as exc:
        return validation_error({exc.field: exc.message})

    record_event(
        session,
        AuditEventType.CONFIG_CHANGE,
        actor_id=account.id,
        detail={"action": "update_security_settings", "fields": sorted(body.keys())},
    )
    session.commit()
    return result

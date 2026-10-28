"""Admin user management (FR-026-FR-034). See contracts/http-api-delta.md."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from asset_dashboard.audit.log import record_event
from asset_dashboard.auth import sessions as sessions_module
from asset_dashboard.auth.authz import require_admin
from asset_dashboard.auth.passwords import hash_password, validate_password_policy
from asset_dashboard.db.base import get_session
from asset_dashboard.db.models import (
    AuditEventType,
    OperatorAccount,
    OperatorAccountRole,
    OperatorAccountStatus,
)
from asset_dashboard.settings_store.service import get_effective_value
from asset_dashboard.web.errors import api_error, validation_error

router = APIRouter(prefix="/api/users")


class UserCreateIn(BaseModel):
    username: str
    password: str
    role: OperatorAccountRole = OperatorAccountRole.OPERATOR


class UserUpdateIn(BaseModel):
    role: OperatorAccountRole | None = None
    status: OperatorAccountStatus | None = None


class ResetPasswordIn(BaseModel):
    new_password: str


def _serialize(account: OperatorAccount) -> dict:
    return {
        "id": account.id,
        "username": account.username,
        "role": account.role.value,
        "status": account.status.value,
    }


def _count_active_admins(session: Session, exclude_id: str | None = None) -> int:
    query = session.query(OperatorAccount).filter(
        OperatorAccount.role == OperatorAccountRole.ADMINISTRATOR,
        OperatorAccount.status == OperatorAccountStatus.ACTIVE,
    )
    if exclude_id:
        query = query.filter(OperatorAccount.id != exclude_id)
    return query.count()


@router.get("")
def api_list_users(
    session: Session = Depends(get_session),
    _account: OperatorAccount = Depends(require_admin),
):
    accounts = session.query(OperatorAccount).order_by(OperatorAccount.username).all()
    return [_serialize(a) for a in accounts]


@router.post("", status_code=201)
def api_create_user(
    body: UserCreateIn,
    session: Session = Depends(get_session),
    account: OperatorAccount = Depends(require_admin),
):
    min_length = get_effective_value(session, "password_min_length")
    errors = validate_password_policy(body.password, min_length=min_length)
    if errors:
        return validation_error({"password": "; ".join(errors)})

    existing = session.query(OperatorAccount).filter_by(username=body.username).one_or_none()
    if existing is not None:
        return validation_error({"username": "Username already exists."})

    new_account = OperatorAccount(
        username=body.username,
        password_hash=hash_password(body.password),
        role=body.role,
    )
    session.add(new_account)
    record_event(
        session,
        AuditEventType.ACCOUNT_CHANGE,
        actor_id=account.id,
        detail={"action": "create", "username": body.username, "role": body.role.value},
    )
    session.commit()
    return _serialize(new_account)


@router.put("/{account_id}")
def api_update_user(
    account_id: str,
    body: UserUpdateIn,
    session: Session = Depends(get_session),
    account: OperatorAccount = Depends(require_admin),
):
    target = session.get(OperatorAccount, account_id)
    if target is None:
        return JSONResponse(status_code=404, content=api_error("not_found", "User not found."))

    would_remove_last_admin = (
        target.role == OperatorAccountRole.ADMINISTRATOR
        and target.status == OperatorAccountStatus.ACTIVE
        and (
            (body.role is not None and body.role != OperatorAccountRole.ADMINISTRATOR)
            or (body.status is not None and body.status != OperatorAccountStatus.ACTIVE)
        )
        and _count_active_admins(session, exclude_id=target.id) == 0
    )
    if would_remove_last_admin:
        return JSONResponse(
            status_code=409,
            content=api_error(
                "last_admin", "At least one active Administrator account must always exist."
            ),
        )

    was_active = target.status == OperatorAccountStatus.ACTIVE
    if body.role is not None:
        target.role = body.role
    if body.status is not None:
        target.status = body.status
    session.add(target)

    record_event(
        session,
        AuditEventType.ACCOUNT_CHANGE,
        actor_id=account.id,
        detail={
            "action": "update",
            "username": target.username,
            "role": target.role.value,
            "status": target.status.value,
        },
    )
    session.commit()

    if was_active and target.status != OperatorAccountStatus.ACTIVE:
        sessions_module.session_store.destroy_for_username(target.username)

    return _serialize(target)


@router.post("/{account_id}/reset-password", status_code=204)
def api_reset_password(
    account_id: str,
    body: ResetPasswordIn,
    session: Session = Depends(get_session),
    account: OperatorAccount = Depends(require_admin),
):
    target = session.get(OperatorAccount, account_id)
    if target is None:
        return JSONResponse(status_code=404, content=api_error("not_found", "User not found."))

    min_length = get_effective_value(session, "password_min_length")
    errors = validate_password_policy(body.new_password, min_length=min_length)
    if errors:
        return validation_error({"new_password": "; ".join(errors)})

    target.password_hash = hash_password(body.new_password)
    session.add(target)
    record_event(
        session,
        AuditEventType.ACCOUNT_CHANGE,
        actor_id=account.id,
        detail={"action": "reset_password", "username": target.username},
    )
    session.commit()

    sessions_module.session_store.destroy_for_username(target.username)
    return Response(status_code=204)

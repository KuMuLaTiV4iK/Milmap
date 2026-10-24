"""Auth + account routes (FR-001-FR-006). See contracts/http-api.md."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from asset_dashboard.audit.log import record_event
from asset_dashboard.auth import sessions as sessions_module
from asset_dashboard.auth.authz import get_current_account
from asset_dashboard.auth.passwords import hash_password, validate_password_policy, verify_password
from asset_dashboard.auth.sessions import clear_session_cookies, set_session_cookies
from asset_dashboard.auth.throttle import is_locked, record_failure, record_success
from asset_dashboard.db.base import get_session
from asset_dashboard.db.models import AuditEventType, OperatorAccount
from asset_dashboard.settings_store.service import get_effective_value
from asset_dashboard.web.errors import api_error, validation_error
from asset_dashboard.web.templating import templates

router = APIRouter()


@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {})


class LoginRequest(BaseModel):
    username: str
    password: str


class CreateAccountRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    current: str
    new: str


class SelfPasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/api/auth/login")
def login(body: LoginRequest, response: Response, session: Session = Depends(get_session)):
    account = session.query(OperatorAccount).filter_by(username=body.username).one_or_none()

    if account is None:
        # Do not reveal whether the username exists.
        return JSONResponse(
            status_code=401,
            content=api_error("invalid_credentials", "Invalid username or password."),
        )

    if is_locked(account):
        record_event(
            session,
            AuditEventType.LOCKOUT,
            actor_id=account.id,
            detail={"username": account.username},
        )
        session.commit()
        return JSONResponse(
            status_code=429,
            content=api_error("account_locked", "Account temporarily locked. Try again later."),
        )

    if not verify_password(account.password_hash, body.password):
        record_failure(session, account)
        record_event(
            session,
            AuditEventType.SIGNIN_FAILURE,
            actor_id=account.id,
            detail={"username": account.username},
        )
        session.commit()
        return JSONResponse(
            status_code=401,
            content=api_error("invalid_credentials", "Invalid username or password."),
        )

    record_success(session, account)
    record_event(
        session,
        AuditEventType.SIGNIN_SUCCESS,
        actor_id=account.id,
        detail={"username": account.username},
    )
    session.commit()

    session_id = sessions_module.session_store.create(account.username)
    json_response = JSONResponse(status_code=200, content={"ok": True})
    set_session_cookies(json_response, session_id)
    return json_response


@router.post("/api/auth/logout")
def logout(request: Request, response: Response):
    from asset_dashboard.auth.sessions import SESSION_COOKIE_NAME

    sessions_module.session_store.destroy(request.cookies.get(SESSION_COOKIE_NAME))
    json_response = JSONResponse(status_code=200, content={"ok": True})
    clear_session_cookies(json_response)
    return json_response


@router.post("/api/account/password", status_code=204)
def change_own_password(
    body: SelfPasswordChangeRequest,
    session: Session = Depends(get_session),
    account: OperatorAccount = Depends(get_current_account),
):
    """Self-service password change for any signed-in account (FR-026)."""
    if not verify_password(account.password_hash, body.current_password):
        return JSONResponse(
            status_code=401,
            content=api_error("invalid_credentials", "Current password is incorrect."),
        )

    min_length = get_effective_value(session, "password_min_length")
    errors = validate_password_policy(body.new_password, min_length=min_length)
    if errors:
        return validation_error({"new_password": "; ".join(errors)})

    account.password_hash = hash_password(body.new_password)
    session.add(account)
    record_event(
        session,
        AuditEventType.ACCOUNT_CHANGE,
        actor_id=account.id,
        detail={"action": "password_change", "username": account.username},
    )
    session.commit()
    return Response(status_code=204)


@router.post("/api/accounts", status_code=201)
def create_account(body: CreateAccountRequest, session: Session = Depends(get_session)):
    min_length = get_effective_value(session, "password_min_length")
    errors = validate_password_policy(body.password, min_length=min_length)
    if errors:
        return validation_error({"password": "; ".join(errors)})

    existing = session.query(OperatorAccount).filter_by(username=body.username).one_or_none()
    if existing is not None:
        return validation_error({"username": "Username already exists."})

    account = OperatorAccount(username=body.username, password_hash=hash_password(body.password))
    session.add(account)
    record_event(
        session,
        AuditEventType.ACCOUNT_CHANGE,
        detail={"action": "create", "username": body.username},
    )
    session.commit()
    return {"id": account.id, "username": account.username}


@router.post("/api/accounts/{account_id}/password", status_code=204)
def change_password(
    account_id: str, body: ChangePasswordRequest, session: Session = Depends(get_session)
):
    account = session.get(OperatorAccount, account_id)
    if account is None:
        return JSONResponse(
            status_code=404, content=api_error("not_found", "Account not found.")
        )

    if not verify_password(account.password_hash, body.current):
        return JSONResponse(
            status_code=401,
            content=api_error("invalid_credentials", "Current password is incorrect."),
        )

    errors = validate_password_policy(body.new)
    if errors:
        # Old credential remains in force — nothing is changed.
        return validation_error({"new": "; ".join(errors)})

    account.password_hash = hash_password(body.new)
    session.add(account)
    record_event(
        session,
        AuditEventType.ACCOUNT_CHANGE,
        actor_id=account.id,
        detail={"action": "password_change", "username": account.username},
    )
    session.commit()
    return Response(status_code=204)

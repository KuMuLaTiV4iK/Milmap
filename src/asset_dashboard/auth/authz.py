"""Role-based access control (FR-027, FR-028, FR-031, FR-033).

Two roles only (Administrator, Operator) — no granular RBAC (YAGNI,
constitution Principle VI). `require_admin` gates user management,
security settings, and NSE allow-list editing. `require_operator` is the
baseline authenticated-account dependency (an Administrator also
satisfies it — the roles are not mutually exclusive in capability, only
Administrator is a superset).
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from asset_dashboard.db.base import get_session
from asset_dashboard.db.models import OperatorAccount, OperatorAccountRole, OperatorAccountStatus
from asset_dashboard.web.errors import api_error


def get_current_account(
    request: Request, session: Session = Depends(get_session)
) -> OperatorAccount:
    """Resolve the signed-in account. The auth-gate middleware already
    guarantees a valid session for any reachable route, so a missing/
    unknown account here means the account was deleted mid-session."""
    username = getattr(request.state, "user", None)
    account = (
        session.query(OperatorAccount).filter_by(username=username).one_or_none()
        if username
        else None
    )
    if account is None or account.status != OperatorAccountStatus.ACTIVE:
        raise HTTPException(
            status_code=401, detail=api_error("unauthenticated", "Sign-in required.")
        )
    return account


def require_operator(
    account: OperatorAccount = Depends(get_current_account),
) -> OperatorAccount:
    """Any active, authenticated account (Operator or Administrator)."""
    return account


def require_admin(
    account: OperatorAccount = Depends(get_current_account),
) -> OperatorAccount:
    if account.role != OperatorAccountRole.ADMINISTRATOR:
        raise HTTPException(
            status_code=403, detail=api_error("forbidden", "Administrator role required.")
        )
    return account


def session_context(request: Request, session: Session) -> dict:
    """Common template context for every server-rendered page: the signed-in
    username plus their role, so `base.html` can hide admin-only nav entries
    from Operators (FR-027, FR-028)."""
    username = getattr(request.state, "user", None)
    role = None
    if username:
        account = session.query(OperatorAccount).filter_by(username=username).one_or_none()
        role = account.role.value if account else None
    return {"session_user": username, "session_role": role}

"""Append-only audit logging helper (FR-006, constitution Principle IV).

`detail` MUST NEVER contain secrets — passwords, attempted default
credentials, etc. (FR-039). Credential-check events should record
attempt counts and timestamps (to verify the Device-Safety Invariants,
SC-008), never the attempted secret itself.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from asset_dashboard.db.models import AuditEventType, AuditLogEntry

_FORBIDDEN_DETAIL_KEYS = {"password", "secret", "credential", "passwd"}


def _assert_no_secrets(detail: dict) -> None:
    lowered = {k.lower() for k in detail}
    leaked = lowered & _FORBIDDEN_DETAIL_KEYS
    if leaked:
        raise ValueError(f"audit detail must not contain secret-like keys: {leaked}")


def record_event(
    session: Session,
    event_type: AuditEventType,
    *,
    actor_id: str | None = None,
    detail: dict | None = None,
) -> AuditLogEntry:
    """Append one audit event. Caller's session transaction controls commit."""
    detail = detail or {}
    _assert_no_secrets(detail)
    entry = AuditLogEntry(event_type=event_type, actor_id=actor_id, detail=detail)
    session.add(entry)
    session.flush()
    return entry

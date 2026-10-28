"""Sign-in failure throttling/lockout (FR-004, FR-032).

Resists brute-force guessing: after the effective `lockout_threshold`
consecutive failures, the account is locked until the effective
`lockout_duration_seconds` has elapsed. Both are admin-editable at
runtime via settings_store (floored/validated there), falling back to
config.py defaults when unset.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from asset_dashboard.db.models import OperatorAccount, utcnow
from asset_dashboard.settings_store.service import get_effective_value


def is_locked(account: OperatorAccount) -> bool:
    return account.lock_until is not None and account.lock_until > utcnow()


def record_failure(session: Session, account: OperatorAccount) -> None:
    threshold = get_effective_value(session, "lockout_threshold")
    duration = get_effective_value(session, "lockout_duration_seconds")
    account.failed_attempts += 1
    if account.failed_attempts >= threshold:
        account.lock_until = utcnow() + timedelta(seconds=duration)
    session.add(account)
    session.flush()


def record_success(session: Session, account: OperatorAccount) -> None:
    account.failed_attempts = 0
    account.lock_until = None
    session.add(account)
    session.flush()

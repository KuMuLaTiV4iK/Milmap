"""DB-backed, admin-editable security settings (FR-032).

A small key/value store (`SecuritySetting`) seeded implicitly from
`config.py` defaults — an unset key simply falls back to its config
default on read, so a fresh install needs no explicit seeding step.
`password_min_length` can never be stored below the hard floor of 20,
enforced here in the update path (not merely the UI), per the
constitution's non-lowerable password-policy requirement.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from asset_dashboard.config import settings
from asset_dashboard.db.models import SecuritySetting

PASSWORD_MIN_LENGTH_FLOOR = 20

_DEFAULTS: dict[str, int] = {
    "password_min_length": settings.min_password_length,
    "lockout_threshold": settings.signin_failure_threshold,
    "lockout_duration_seconds": settings.signin_lockout_seconds,
    "session_idle_timeout_seconds": settings.session_idle_timeout_seconds,
}

_POSITIVE_KEYS = {"lockout_threshold", "lockout_duration_seconds", "session_idle_timeout_seconds"}


class SettingsValidationError(ValueError):
    def __init__(self, field: str, message: str) -> None:
        self.field = field
        self.message = message
        super().__init__(message)


def get_effective_settings(session: Session) -> dict[str, int]:
    """All four settings, falling back to config.py defaults for any key
    with no stored row yet."""
    rows = {row.key: row.value for row in session.query(SecuritySetting).all()}
    return {key: rows.get(key, default) for key, default in _DEFAULTS.items()}


def get_effective_value(session: Session, key: str) -> int:
    row = session.get(SecuritySetting, key)
    return row.value if row is not None else _DEFAULTS[key]


def update_settings(session: Session, updates: dict[str, int]) -> dict[str, int]:
    """Validate and persist a subset of settings. Raises
    SettingsValidationError on the first invalid field (caller maps this
    to a 422)."""
    for key in updates:
        if key not in _DEFAULTS:
            raise SettingsValidationError(key, f"unknown setting '{key}'")

    if "password_min_length" in updates:
        value = updates["password_min_length"]
        if not isinstance(value, int) or value < PASSWORD_MIN_LENGTH_FLOOR:
            raise SettingsValidationError(
                "password_min_length", f"must be at least {PASSWORD_MIN_LENGTH_FLOOR}"
            )

    for key in _POSITIVE_KEYS & updates.keys():
        value = updates[key]
        if not isinstance(value, int) or value <= 0:
            raise SettingsValidationError(key, "must be a positive integer")

    for key, value in updates.items():
        row = session.get(SecuritySetting, key)
        if row is None:
            row = SecuritySetting(key=key, value=value)
        else:
            row.value = value
        session.add(row)
    session.flush()

    return get_effective_settings(session)

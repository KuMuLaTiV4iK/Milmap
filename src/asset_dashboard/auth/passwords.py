"""Argon2id password hashing + password policy (FR-002, FR-003).

Policy: minimum length 20 characters, enforced at account creation AND at
every password change. Passwords are never stored in plaintext or any
recoverable form — only as an Argon2id hash.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from asset_dashboard.config import settings

_hasher = PasswordHasher()


def validate_password_policy(password: str, *, min_length: int | None = None) -> list[str]:
    """Return a list of human-readable policy violations (empty = OK).

    `min_length` lets a caller pass the *effective* setting (admin-editable
    at runtime via settings_store, floored at 20 — FR-032); callers with no
    DB session handy (e.g. the CLI bootstrap) fall back to the config.py
    default.
    """
    effective_min_length = min_length if min_length is not None else settings.min_password_length
    errors: list[str] = []
    if len(password) < effective_min_length:
        errors.append(f"Password must be at least {effective_min_length} characters long.")
    return errors


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(hashed: str, candidate: str) -> bool:
    try:
        return _hasher.verify(hashed, candidate)
    except VerifyMismatchError:
        return False

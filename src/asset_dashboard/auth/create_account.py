"""CLI bootstrap helper: create the first operator account.

Usage:
    python -m asset_dashboard.auth.create_account --username admin
(prompts for a password meeting the >=20-char policy; never echoes it)
"""
from __future__ import annotations

import argparse
import getpass
import sys

from asset_dashboard.audit.log import record_event
from asset_dashboard.auth.passwords import hash_password, validate_password_policy
from asset_dashboard.db.base import session_scope
from asset_dashboard.db.models import AuditEventType, OperatorAccount, OperatorAccountRole


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a local operator account.")
    parser.add_argument("--username", required=True)
    args = parser.parse_args()

    password = getpass.getpass("New password (>= 20 characters): ")
    errors = validate_password_policy(password)
    if errors:
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        return 1

    confirm = getpass.getpass("Confirm password: ")
    if confirm != password:
        print("error: passwords do not match", file=sys.stderr)
        return 1

    with session_scope() as session:
        existing = session.query(OperatorAccount).filter_by(username=args.username).one_or_none()
        if existing is not None:
            print(f"error: username '{args.username}' already exists", file=sys.stderr)
            return 1

        # FR-030: the first account on a fresh install becomes Administrator;
        # every subsequent account defaults to Operator.
        is_first_account = session.query(OperatorAccount).count() == 0
        role = (
            OperatorAccountRole.ADMINISTRATOR
            if is_first_account
            else OperatorAccountRole.OPERATOR
        )

        account = OperatorAccount(
            username=args.username, password_hash=hash_password(password), role=role
        )
        session.add(account)
        record_event(
            session,
            AuditEventType.ACCOUNT_CHANGE,
            detail={
                "action": "create",
                "username": args.username,
                "via": "cli",
                "role": role.value,
            },
        )

    print(f"Created account '{args.username}' (role: {role.value}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

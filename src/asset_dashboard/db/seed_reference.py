"""Load the offline reference datasets into the database (FR-040).

Usage:
    python -m asset_dashboard.db.seed_reference

Re-running replaces existing rows (idempotent re-seed from the JSON files
under data/reference/, which are the locally-maintained source of truth).
"""

from __future__ import annotations

import json

from asset_dashboard.config import REFERENCE_DIR
from asset_dashboard.db.base import session_scope
from asset_dashboard.db.models import DefaultCredentialEntry, ReferenceVersionEntry
from asset_dashboard.nse.allowlist import seed_default_allowlist


def seed() -> tuple[int, int, int]:
    version_entries = json.loads((REFERENCE_DIR / "version_validity.json").read_text())
    credential_entries = json.loads((REFERENCE_DIR / "default_credentials.json").read_text())

    with session_scope() as session:
        session.query(ReferenceVersionEntry).delete()
        for entry in version_entries:
            session.add(ReferenceVersionEntry(source="manual", **entry))

        session.query(DefaultCredentialEntry).delete()
        for entry in credential_entries:
            session.add(DefaultCredentialEntry(**entry))

        n_scripts = seed_default_allowlist(session)

    return len(version_entries), len(credential_entries), n_scripts


if __name__ == "__main__":
    n_versions, n_creds, n_scripts = seed()
    print(
        f"Seeded {n_versions} version-validity entries, {n_creds} default-credential entries, "
        f"and {n_scripts} NSE allow-list entries."
    )

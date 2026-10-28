"""CRUD for the offline minimum-version threshold dataset (FR-009-FR-011,
V0.7). Operational compliance data, editable by Operators and
Administrators alike — see plan.md's Constitution Check note on why this
is not a Principle VII admin-only surface."""

from __future__ import annotations

from sqlalchemy.orm import Session

from asset_dashboard.compliance.version_compare import parse_version
from asset_dashboard.db.models import ReferenceVersionEntry


class ReferenceVersionNotFoundError(Exception):
    pass


def validate_reference_version(payload: dict) -> str | None:
    if not payload.get("vendor"):
        return "vendor is required."
    # `type` is free-form classification text (never part of compliance
    # matching, see compliance/version_check.py) — not restricted to a
    # fixed enum, since real vendor catalogs need categories/sub-tracks
    # (e.g. a UCM's separately versioned "System" vs "PBX" firmware) a
    # small fixed list can't anticipate. Only non-empty is required.
    if not (payload.get("type") or "").strip():
        return "type is required."
    min_version = payload.get("min_version")
    if not min_version:
        return "min_version is required."
    if parse_version(min_version) is None:
        return "min_version must be a comparator-parseable version."
    return None


def list_entries(session: Session) -> list[ReferenceVersionEntry]:
    return (
        session.query(ReferenceVersionEntry)
        .order_by(ReferenceVersionEntry.vendor, ReferenceVersionEntry.model)
        .all()
    )


def get_entry(session: Session, entry_id: str) -> ReferenceVersionEntry:
    entry = session.get(ReferenceVersionEntry, entry_id)
    if entry is None:
        raise ReferenceVersionNotFoundError(entry_id)
    return entry


def create_entry(session: Session, payload: dict) -> ReferenceVersionEntry:
    entry = ReferenceVersionEntry(
        vendor=payload["vendor"],
        type=payload["type"],
        model=payload.get("model"),
        min_version=payload["min_version"],
        note=payload.get("note"),
        source="manual",
    )
    session.add(entry)
    session.flush()
    return entry


def update_entry(session: Session, entry_id: str, payload: dict) -> ReferenceVersionEntry:
    entry = get_entry(session, entry_id)
    entry.vendor = payload["vendor"]
    entry.type = payload["type"]
    entry.model = payload.get("model")
    entry.min_version = payload["min_version"]
    entry.note = payload.get("note")
    entry.needs_review = False
    return entry


def delete_entry(session: Session, entry_id: str) -> None:
    entry = get_entry(session, entry_id)
    session.delete(entry)

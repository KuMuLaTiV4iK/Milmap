"""Tracked ingestion-source CRUD + bundle import preview/apply (FR-014,
FR-016-FR-021; contracts/http-api-delta.md §B/§C). This module verifies
and applies an already-produced bundle — it never fetches anything
itself (that is `tools/version_fetcher/`'s job, on a different machine).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from asset_dashboard.compliance.version_compare import compare_versions
from asset_dashboard.db.models import ReferenceVersionEntry, VersionIngestionSource
from asset_dashboard.version_ingestion.bundle import BundleInvalidError, verify_bundle

__all__ = [
    "BundleInvalidError",
    "SourceNotFoundError",
    "create_source",
    "delete_source",
    "get_source",
    "list_sources",
    "preview_import",
    "apply_import",
    "update_source",
]


class SourceNotFoundError(Exception):
    pass


def list_sources(session: Session) -> list[VersionIngestionSource]:
    return session.query(VersionIngestionSource).order_by(VersionIngestionSource.vendor).all()


def get_source(session: Session, source_id: str) -> VersionIngestionSource:
    source = session.get(VersionIngestionSource, source_id)
    if source is None:
        raise SourceNotFoundError(source_id)
    return source


def validate_source(payload: dict) -> str | None:
    if not payload.get("vendor"):
        return "vendor is required."
    if not payload.get("source_url"):
        return "source_url is required."
    if not payload.get("models"):
        return "models must be a non-empty list."
    return None


def create_source(
    session: Session, payload: dict, created_by: str | None
) -> VersionIngestionSource:
    source = VersionIngestionSource(
        vendor=payload["vendor"],
        source_url=payload["source_url"],
        models=payload["models"],
        extractor=payload.get("extractor") or {},
        created_by=created_by,
    )
    session.add(source)
    session.flush()
    return source


def update_source(session: Session, source_id: str, payload: dict) -> VersionIngestionSource:
    source = get_source(session, source_id)
    source.vendor = payload["vendor"]
    source.source_url = payload["source_url"]
    source.models = payload["models"]
    source.extractor = payload.get("extractor") or {}
    return source


def delete_source(session: Session, source_id: str) -> None:
    source = get_source(session, source_id)
    session.delete(source)


def _find_current_entry(
    session: Session, vendor: str, model: str | None, device_type: str | None
) -> ReferenceVersionEntry | None:
    """Keyed on (vendor, model, type) — NOT just (vendor, model) — since a
    single vendor/model can carry more than one independently versioned
    firmware track (e.g. a UCM's "System" vs "PBX" firmware), each its own
    `type` value and its own threshold row. `type` plays no role in
    compliance matching (compliance/version_check.py still matches on
    vendor+model only); this key only controls import create-vs-update
    dedup, so two tracks never silently clobber each other."""
    query = session.query(ReferenceVersionEntry).filter_by(vendor=vendor, type=device_type)
    query = query.filter_by(model=model) if model else query.filter(
        ReferenceVersionEntry.model.is_(None)
    )
    return query.one_or_none()


def preview_import(
    session: Session, raw_bundle: str | bytes, keys: dict[str, bytes]
) -> dict:
    """Verify the bundle (no writes) and return a review/diff
    (contracts/http-api-delta.md §C). Raises BundleInvalidError —
    unverified — on any integrity/authenticity failure."""
    bundle = verify_bundle(raw_bundle, keys)
    payload = bundle["payload"]
    vendor = payload["vendor"]

    changes = []
    verdict_changing = 0
    for entry in payload["entries"]:
        model = entry.get("model")
        if entry["status"] != "ok":
            changes.append(
                {"model": model, "status": "failed", "reason": entry.get("reason")}
            )
            continue

        current = _find_current_entry(session, vendor, model, entry.get("type"))
        incoming = entry["version"]
        current_version = current.min_version if current else None
        comparison = (
            compare_versions(incoming, current_version) if current_version else None
        )
        downgrade = comparison is not None and comparison < 0
        effect = "create" if current is None else "update"
        changes.append(
            {
                "model": model,
                "type": entry.get("type"),
                "current": current_version,
                "incoming": incoming,
                "effect": effect,
                "downgrade": downgrade,
            }
        )
        if downgrade:
            verdict_changing += 1

    return {
        "vendor": vendor,
        "bundle_digest": bundle["integrity"]["digest"],
        "changes": changes,
        "verdict_changing": verdict_changing,
    }


def apply_import(
    session: Session,
    raw_bundle: str | bytes,
    keys: dict[str, bytes],
    *,
    source_id: str | None,
    confirm_downgrade: bool,
) -> dict:
    """Re-verify the bundle server-side and apply create/update to
    threshold rows (contracts/http-api-delta.md §C, FR-017/FR-018/FR-020).
    `status != ok` entries are skipped, never written. Apparent downgrades
    require `confirm_downgrade`; otherwise the row is written with
    `needs_review=true` for a later confirmation."""
    bundle = verify_bundle(raw_bundle, keys)
    payload = bundle["payload"]
    vendor = payload["vendor"]
    digest = bundle["integrity"]["digest"]

    created = 0
    updated = 0
    skipped_failed = 0
    flagged_downgrade = 0

    for entry in payload["entries"]:
        if entry["status"] != "ok":
            skipped_failed += 1
            continue

        model = entry.get("model")
        incoming = entry["version"]
        current = _find_current_entry(session, vendor, model, entry.get("type"))
        current_version = current.min_version if current else None
        comparison = (
            compare_versions(incoming, current_version) if current_version else None
        )
        is_downgrade = comparison is not None and comparison < 0
        needs_review = is_downgrade and not confirm_downgrade

        if current is None:
            session.add(
                ReferenceVersionEntry(
                    vendor=vendor,
                    type=entry.get("type"),
                    model=model,
                    min_version=incoming,
                    source="ingested",
                    source_ref=source_id or vendor,
                    needs_review=needs_review,
                )
            )
            created += 1
        else:
            current.min_version = incoming
            current.type = entry.get("type")
            current.source = "ingested"
            current.source_ref = source_id or vendor
            current.needs_review = needs_review
            updated += 1

        if needs_review:
            flagged_downgrade += 1

    if source_id:
        source = session.get(VersionIngestionSource, source_id)
        if source is not None:
            source.last_import_status = "ok" if skipped_failed == 0 else "partial"
            source.last_import_at = datetime.utcnow()
            # Keyed "model:type" (not just "model") so two independently
            # versioned tracks on the same model (e.g. a UCM's "System" vs
            # "PBX" firmware) both show up instead of one overwriting the
            # other in this display-only summary.
            source.last_versions = {
                f"{e.get('model')}:{e.get('type')}": e.get("version")
                for e in payload["entries"]
                if e["status"] == "ok"
            }

    return {
        "vendor": vendor,
        "bundle_digest": digest,
        "created": created,
        "updated": updated,
        "skipped_failed": skipped_failed,
        "flagged_downgrade": flagged_downgrade,
    }

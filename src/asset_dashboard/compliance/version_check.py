"""Offline minimum-version threshold check (FR-001-FR-008, V0.7).

Evaluated entirely against the locally maintained reference dataset (a
local SQLite query) plus the in-memory comparator — this function makes NO
network or external call of any kind, consistent with the air-gapped
deployment (FR-008).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from asset_dashboard.compliance.version_compare import compare_versions
from asset_dashboard.db.models import ReferenceVersionEntry

_RESULT_COMPLIANT = "compliant"
_RESULT_NON_COMPLIANT = "non_compliant"
_RESULT_UNKNOWN = "unknown"


def _find_threshold(session: Session, lowered_haystack: str) -> ReferenceVersionEntry | None:
    """Best match against `vendor` (+`model`) — NOT `type`: a device-type
    category (e.g. "IP-Phone") cannot be expected to appear in a scanned
    service/firmware banner, so it plays no role in matching. A
    model-specific entry whose model text also appears in the haystack
    wins over a vendor-wide entry; ties break on the longest vendor name.
    """
    entries = (
        session.query(ReferenceVersionEntry)
        .filter(ReferenceVersionEntry.min_version.isnot(None))
        .all()
    )
    candidates = [e for e in entries if e.vendor.lower() in lowered_haystack]
    if not candidates:
        return None
    candidates.sort(key=lambda e: len(e.vendor), reverse=True)

    model_matches = [e for e in candidates if e.model and e.model.lower() in lowered_haystack]
    if model_matches:
        return model_matches[0]
    return next((e for e in candidates if not e.model), candidates[0])


def check_version(session: Session, version_string: str | None) -> tuple[str, dict]:
    """Returns (result, detail) where result is 'compliant' | 'non_compliant'
    | 'unknown'.

    `detail` carries `checked_version`, `threshold`, `matched_vendor`,
    `matched_model`, `expected_valid` (the threshold as an upgrade target),
    and `comparison` in {below_threshold, at_or_above, not_comparable,
    no_threshold}. This detail is frozen into the caller's finding — an
    immutable record of the inputs in effect at scan time (FR-012a).
    """
    if not version_string:
        return _RESULT_UNKNOWN, {"reason": "no version detected", "comparison": "no_threshold"}

    lowered = version_string.lower()
    candidate_version = version_string.split()[-1]

    entry = _find_threshold(session, lowered)
    if entry is None:
        return _RESULT_UNKNOWN, {
            "reason": "no threshold on file for this vendor/model",
            "version_string": version_string,
            "checked_version": candidate_version,
            "comparison": "no_threshold",
        }

    comparison = compare_versions(candidate_version, entry.min_version)
    expected_valid = " ".join(filter(None, [entry.vendor, entry.model, entry.min_version]))
    detail = {
        "checked_version": candidate_version,
        "threshold": entry.min_version,
        "matched_vendor": entry.vendor,
        "matched_model": entry.model,
        "expected_valid": expected_valid,
        "note": entry.note,
    }

    if comparison is None:
        detail["comparison"] = "not_comparable"
        return _RESULT_UNKNOWN, detail

    if comparison < 0:
        detail["comparison"] = "below_threshold"
        return _RESULT_NON_COMPLIANT, detail

    detail["comparison"] = "at_or_above"
    return _RESULT_COMPLIANT, detail

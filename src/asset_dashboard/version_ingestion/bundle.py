"""Update-bundle parsing + integrity/authenticity verification (FR-016,
FR-016a; contracts/bundle-format.md). Pure, offline, in-memory — this
module performs NO network access; it only verifies a bundle a human
carried over from the separate staging machine.

NOTE (temporary, per explicit request): the `integrity` envelope
(SHA-256 digest + pre-shared-key HMAC) is now OPTIONAL rather than
required, so a hand-composed bundle can be imported while the signing
tooling isn't in place yet. When `integrity` IS present, it is still
fully verified (unchanged behavior) — a tampered or wrongly-keyed
signed bundle is still rejected. Re-tighten this to required once bundle
signing is wired up end-to-end (FR-016a's "MUST be verified" reverts to
being enforced unconditionally).
"""
from __future__ import annotations

import hashlib
import hmac
import json

SCHEMA = "milmap.version-bundle/1"
ENTRY_STATUSES = {"ok", "failed"}


class BundleInvalidError(Exception):
    """Raised for any parse/integrity/authenticity failure. The caller MUST
    make no threshold write when this is raised (FR-016a)."""


def canonicalize_payload(payload: dict) -> bytes:
    """Canonical byte form of `payload`: sorted keys, no insignificant
    whitespace, UTF-8 — the exact bytes both the staging fetcher and this
    importer hash/HMAC (contracts/bundle-format.md rule 1)."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _digest(payload_bytes: bytes) -> str:
    return hashlib.sha256(payload_bytes).hexdigest()


def _mac(payload_bytes: bytes, key: bytes) -> str:
    return hmac.new(key, payload_bytes, hashlib.sha256).hexdigest()


def parse_bundle(raw: str | bytes) -> dict:
    """Parse the bundle's outer JSON structure. Raises BundleInvalidError on
    unparseable JSON, an unknown/missing `schema`, or a missing top-level
    field — never guesses a shape. `integrity` is optional (see module
    note); when present it must be well-formed."""
    try:
        bundle = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise BundleInvalidError("bundle is not valid JSON") from exc

    if not isinstance(bundle, dict):
        raise BundleInvalidError("bundle must be a JSON object")

    if bundle.get("schema") != SCHEMA:
        raise BundleInvalidError(f"unknown or missing bundle schema (expected {SCHEMA})")

    payload = bundle.get("payload")
    if not isinstance(payload, dict):
        raise BundleInvalidError("bundle is missing payload")

    integrity = bundle.get("integrity")
    if integrity is not None:
        if not isinstance(integrity, dict):
            raise BundleInvalidError("integrity, if present, must be an object")
        for field in ("alg", "digest", "mac", "key_id"):
            if field not in integrity:
                raise BundleInvalidError(f"integrity is missing required field: {field}")
        if integrity["alg"] != "HMAC-SHA256":
            raise BundleInvalidError(f"unsupported integrity algorithm: {integrity['alg']!r}")

    for field in ("vendor", "generated_at", "entries"):
        if field not in payload:
            raise BundleInvalidError(f"payload is missing required field: {field}")
    if not isinstance(payload["entries"], list):
        raise BundleInvalidError("payload.entries must be a list")

    for entry in payload["entries"]:
        if not isinstance(entry, dict):
            raise BundleInvalidError("each payload entry must be an object")
        status = entry.get("status")
        if status not in ENTRY_STATUSES:
            raise BundleInvalidError(f"entry has an unknown status: {status!r}")
        if status == "ok" and not entry.get("version"):
            raise BundleInvalidError("an 'ok' entry must carry a version")
        if status == "failed" and not entry.get("reason"):
            raise BundleInvalidError("a 'failed' entry must carry a reason")
        # `type` is required only for an 'ok' entry (mirrors the 'version'
        # rule above) — a 'failed' entry may carry no type at all, e.g.
        # when the failure IS a missing/invalid type (FR-017: one bad
        # model must never invalidate the whole bundle). It is pure
        # classification text (never part of compliance matching — see
        # compliance/version_check.py), so ANY non-empty string is
        # accepted: real vendor catalogs need finer/different categories
        # (e.g. a UCM's separately versioned "System" vs "PBX" firmware
        # tracks) than a small fixed enum can anticipate.
        if status == "ok" and not (entry.get("type") or "").strip():
            raise BundleInvalidError("an 'ok' entry must carry a non-empty type")

    return bundle


def verify_bundle(raw: str | bytes, keys: dict[str, bytes]) -> dict:
    """Parse, and verify integrity/authenticity WHEN the bundle carries an
    `integrity` envelope (see module note — currently optional). Returns
    the bundle dict on success, always carrying a computed
    `integrity.digest` (even for an unsigned bundle, so callers/audit
    detail have a stable content fingerprint). Raises BundleInvalidError
    on ANY mismatch, unknown key_id, missing field, or unparseable JSON —
    no threshold write may follow a raised error (FR-016a)."""
    bundle = parse_bundle(raw)
    payload = bundle["payload"]
    integrity = bundle.get("integrity")

    payload_bytes = canonicalize_payload(payload)
    computed_digest = _digest(payload_bytes)

    if integrity is not None:
        key_id = integrity["key_id"]
        key = keys.get(key_id)
        if key is None:
            raise BundleInvalidError(f"unknown key_id: {key_id!r}")

        if not hmac.compare_digest(computed_digest, integrity["digest"]):
            raise BundleInvalidError("payload digest mismatch")

        expected_mac = _mac(payload_bytes, key)
        if not hmac.compare_digest(expected_mac, integrity["mac"]):
            raise BundleInvalidError("HMAC verification failed")

    bundle["integrity"] = {**(integrity or {}), "digest": computed_digest}
    return bundle


def bundle_digest(bundle: dict) -> str:
    """The bundle's content digest, safe to record in an audit event
    (never the key itself)."""
    return str(bundle["integrity"]["digest"])

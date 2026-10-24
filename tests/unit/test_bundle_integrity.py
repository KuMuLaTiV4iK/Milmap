"""FR-016a, contracts/bundle-format.md: bundle integrity/authenticity
verification. Valid HMAC/digest accepted; tampered payload, wrong
key_id, missing field, unknown schema all rejected; the key never
appears in any output."""
import hashlib
import hmac
import json

import pytest

from asset_dashboard.version_ingestion.bundle import (
    BundleInvalidError,
    bundle_digest,
    canonicalize_payload,
    verify_bundle,
)

KEY_ID = "milmap-2026"
KEY = bytes.fromhex("aa" * 32)
KEYS = {KEY_ID: KEY}


def _make_bundle(payload: dict, *, key: bytes = KEY, key_id: str = KEY_ID) -> dict:
    payload_bytes = canonicalize_payload(payload)
    digest = hashlib.sha256(payload_bytes).hexdigest()
    mac = hmac.new(key, payload_bytes, hashlib.sha256).hexdigest()
    return {
        "schema": "milmap.version-bundle/1",
        "payload": payload,
        "integrity": {"alg": "HMAC-SHA256", "digest": digest, "mac": mac, "key_id": key_id},
    }


def _payload() -> dict:
    return {
        "vendor": "OpenSSH",
        "generated_at": "2026-10-23T10:00:00Z",
        "entries": [
            {
                "model": "portable",
                "type": "router",
                "version": "9.9",
                "source": "https://www.openssh.com/",
                "fetched_at": "2026-10-23T10:00:00Z",
                "status": "ok",
            }
        ],
    }


def test_valid_bundle_is_accepted():
    bundle = _make_bundle(_payload())
    verified = verify_bundle(json.dumps(bundle), KEYS)
    assert verified["payload"]["vendor"] == "OpenSSH"
    assert bundle_digest(verified) == bundle["integrity"]["digest"]


def test_tampered_payload_is_rejected():
    bundle = _make_bundle(_payload())
    bundle["payload"]["entries"][0]["version"] = "99.99"  # tamper after signing
    with pytest.raises(BundleInvalidError):
        verify_bundle(json.dumps(bundle), KEYS)


def test_wrong_key_id_is_rejected():
    bundle = _make_bundle(_payload())
    with pytest.raises(BundleInvalidError):
        verify_bundle(json.dumps(bundle), {"some-other-key": KEY})


def test_signed_with_different_key_is_rejected():
    bundle = _make_bundle(_payload(), key=bytes.fromhex("bb" * 32))
    with pytest.raises(BundleInvalidError):
        verify_bundle(json.dumps(bundle), KEYS)


def test_missing_field_is_rejected():
    bundle = _make_bundle(_payload())
    del bundle["integrity"]["mac"]
    with pytest.raises(BundleInvalidError):
        verify_bundle(json.dumps(bundle), KEYS)


def test_unknown_schema_is_rejected():
    bundle = _make_bundle(_payload())
    bundle["schema"] = "milmap.version-bundle/99"
    with pytest.raises(BundleInvalidError):
        verify_bundle(json.dumps(bundle), KEYS)


def test_unparseable_json_is_rejected():
    with pytest.raises(BundleInvalidError):
        verify_bundle("{not json", KEYS)


def test_failed_entry_without_reason_is_rejected():
    payload = _payload()
    payload["entries"].append({"model": "legacy", "version": None, "status": "failed"})
    bundle = _make_bundle(payload)
    with pytest.raises(BundleInvalidError):
        verify_bundle(json.dumps(bundle), KEYS)


def test_ok_entry_with_empty_type_is_rejected():
    payload = _payload()
    payload["entries"][0]["type"] = ""
    bundle = _make_bundle(payload)
    with pytest.raises(BundleInvalidError):
        verify_bundle(json.dumps(bundle), KEYS)


def test_ok_entry_type_is_free_form_not_a_fixed_enum():
    """`type` is pure classification text — never part of compliance
    matching (compliance/version_check.py) — so real vendor catalogs can
    use categories/sub-tracks a small fixed list can't anticipate (e.g. a
    UCM's separately versioned "System" vs "PBX" firmware)."""
    payload = _payload()
    payload["entries"][0]["type"] = "UCM.Sys"
    bundle = _make_bundle(payload)
    verified = verify_bundle(json.dumps(bundle), KEYS)
    assert verified["payload"]["entries"][0]["type"] == "UCM.Sys"


def test_failed_entry_may_omit_type():
    payload = _payload()
    payload["entries"].append(
        {"model": "legacy", "version": None, "status": "failed", "reason": "no type configured"}
    )
    bundle = _make_bundle(payload)
    verified = verify_bundle(json.dumps(bundle), KEYS)
    assert verified["payload"]["entries"][1]["status"] == "failed"


def test_key_never_appears_in_verified_output():
    bundle = _make_bundle(_payload())
    verified = verify_bundle(json.dumps(bundle), KEYS)
    serialized = json.dumps(verified)
    assert KEY.hex() not in serialized


def test_unsigned_bundle_is_accepted_when_integrity_is_omitted():
    """Temporary (module note): hash/signature checking is optional for
    now, so a hand-composed bundle with no `integrity` block is accepted.
    A computed digest is still attached for audit-trail purposes."""
    bundle = {"schema": "milmap.version-bundle/1", "payload": _payload()}
    verified = verify_bundle(json.dumps(bundle), KEYS)
    assert verified["payload"]["vendor"] == "OpenSSH"
    assert len(verified["integrity"]["digest"]) == 64  # sha256 hex


def test_signed_bundle_is_still_fully_verified_when_integrity_present():
    """Omitting `integrity` is allowed, but a bundle that DOES carry one
    is still checked — a tampered signed bundle is still rejected."""
    bundle = _make_bundle(_payload())
    bundle["payload"]["entries"][0]["version"] = "99.99"
    with pytest.raises(BundleInvalidError):
        verify_bundle(json.dumps(bundle), KEYS)

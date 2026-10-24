"""Write a signed/integrity-checked update bundle (contracts/bundle-format.md).

Canonicalizes `payload`, computes SHA-256 + HMAC-SHA256 with the provided
key, and writes the JSON bundle. The key is never written into the
bundle (FR-016a; contracts/bundle-format.md rule 3).
"""
from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path


def canonicalize_payload(payload: dict) -> bytes:
    """MUST match `asset_dashboard.version_ingestion.bundle.canonicalize_payload`
    byte-for-byte so staging and deployment agree on what was signed."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def build_bundle(payload: dict, key: bytes, key_id: str) -> dict:
    payload_bytes = canonicalize_payload(payload)
    digest = hashlib.sha256(payload_bytes).hexdigest()
    mac = hmac.new(key, payload_bytes, hashlib.sha256).hexdigest()
    return {
        "schema": "milmap.version-bundle/1",
        "payload": payload,
        "integrity": {"alg": "HMAC-SHA256", "digest": digest, "mac": mac, "key_id": key_id},
    }


def write_bundle(payload: dict, key: bytes, key_id: str, out_path: Path) -> None:
    bundle = build_bundle(payload, key, key_id)
    out_path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")

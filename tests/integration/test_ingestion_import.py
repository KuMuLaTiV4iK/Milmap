"""Ingestion import integration tests (FR-014-FR-021): preview/apply happy
path (create + update), failed-entry skip (no write), downgrade/
verdict-changing requires confirmation else needs_review=true, one
CONFIG_CHANGE import audit with provenance and no secret, admin-only
(operator -> 403)."""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from asset_dashboard.config import settings as app_settings
from asset_dashboard.db.base import session_scope
from asset_dashboard.db.models import AuditEventType, AuditLogEntry, ReferenceVersionEntry

KEY_ID = "milmap-2026"
KEY_HEX = "aa" * 32
KEY = bytes.fromhex(KEY_HEX)


def canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def make_bundle(entries: list[dict], vendor: str = "OpenSSH") -> dict:
    payload = {"vendor": vendor, "generated_at": "2026-10-23T10:00:00Z", "entries": entries}
    payload_bytes = canonical(payload)
    digest = hashlib.sha256(payload_bytes).hexdigest()
    mac = hmac.new(KEY, payload_bytes, hashlib.sha256).hexdigest()
    return {
        "schema": "milmap.version-bundle/1",
        "payload": payload,
        "integrity": {"alg": "HMAC-SHA256", "digest": digest, "mac": mac, "key_id": KEY_ID},
    }


def make_unsigned_bundle(entries: list[dict], vendor: str = "OpenSSH") -> dict:
    """No `integrity` block — hash/signature checking is currently
    optional (bundle.py module note); this is the hand-composed shape."""
    payload = {"vendor": vendor, "generated_at": "2026-10-23T10:00:00Z", "entries": entries}
    return {"schema": "milmap.version-bundle/1", "payload": payload}


@pytest.fixture(autouse=True)
def _provision_key(tmp_path, monkeypatch):
    keys_file = tmp_path / "version_ingestion_keys.txt"
    keys_file.write_text(f"{KEY_ID}\t{KEY_HEX}\n")
    monkeypatch.setattr(app_settings, "version_ingestion_keys_file", keys_file)


def test_apply_accepts_an_unsigned_bundle(admin_client):
    bundle = make_unsigned_bundle(
        [
            {
                "model": "portable",
                "type": "router",
                "version": "9.9",
                "source": "x",
                "fetched_at": "x",
                "status": "ok",
            }
        ]
    )
    resp = admin_client.post("/api/version-ingestion/import/apply", json={"bundle": bundle})
    assert resp.status_code == 200, resp.text


def test_apply_accepts_free_form_types_without_rejecting_the_bundle(admin_client):
    """Regression: a real Grandstream catalog uses `type` values like
    "UCM.Sys"/"UCM-PBX" outside any small fixed enum. These must not
    reject the whole bundle (FR-017: one bad model never aborts others —
    here there's nothing bad about it at all, the type is just unusual)."""
    bundle = make_unsigned_bundle(
        [
            {"model": "GCC6010", "type": "UCM.Sys", "version": "1.0.7.71", "status": "ok"},
            {"model": "GCC6010", "type": "UCM-PBX", "version": "1.0.27.94", "status": "ok"},
        ],
        vendor="Grandstream",
    )
    resp = admin_client.post("/api/version-ingestion/import/apply", json={"bundle": bundle})
    assert resp.status_code == 200, resp.text
    assert (
        resp.json()["created"] == 2
    )  # two independently versioned tracks, not one clobbering the other

    with session_scope() as session:
        entries = (
            session.query(ReferenceVersionEntry)
            .filter_by(vendor="Grandstream", model="GCC6010")
            .all()
        )
        by_type = {e.type: e.min_version for e in entries}
        assert by_type == {"UCM.Sys": "1.0.7.71", "UCM-PBX": "1.0.27.94"}


def test_preview_shows_diff_without_writing(admin_client):
    with session_scope() as session:
        session.add(ReferenceVersionEntry(vendor="OpenSSH", type="router", min_version="9.0"))

    bundle = make_bundle(
        [
            {
                "model": "portable",
                "type": "router",
                "version": "9.9",
                "source": "x",
                "fetched_at": "x",
                "status": "ok",
            }
        ]
    )
    resp = admin_client.post("/api/version-ingestion/import/preview", json={"bundle": bundle})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["changes"][0]["incoming"] == "9.9"
    assert body["changes"][0]["effect"] == "create"  # distinct model row

    with session_scope() as session:
        count = session.query(ReferenceVersionEntry).count()
    assert count == 1  # preview made no write


def test_apply_creates_and_updates_entries(admin_client):
    bundle = make_bundle(
        [
            {
                "model": "portable",
                "type": "router",
                "version": "9.9",
                "source": "x",
                "fetched_at": "x",
                "status": "ok",
            }
        ]
    )
    resp = admin_client.post("/api/version-ingestion/import/apply", json={"bundle": bundle})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["created"] == 1
    assert body["skipped_failed"] == 0

    with session_scope() as session:
        entry = session.query(ReferenceVersionEntry).filter_by(vendor="OpenSSH").one()
        assert entry.min_version == "9.9"
        assert entry.source == "ingested"


def test_failed_entry_is_skipped_never_written(admin_client):
    bundle = make_bundle(
        [{"model": "legacy", "version": None, "status": "failed", "reason": "unreachable"}]
    )
    resp = admin_client.post("/api/version-ingestion/import/apply", json={"bundle": bundle})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["skipped_failed"] == 1
    assert body["created"] == 0

    with session_scope() as session:
        assert session.query(ReferenceVersionEntry).count() == 0


def test_downgrade_requires_confirmation_else_needs_review(admin_client):
    with session_scope() as session:
        session.add(ReferenceVersionEntry(vendor="OpenSSH", type="router", min_version="9.5"))

    bundle = make_bundle(
        [
            {
                "model": None,
                "type": "router",
                "version": "9.0",
                "source": "x",
                "fetched_at": "x",
                "status": "ok",
            }
        ]
    )

    resp = admin_client.post("/api/version-ingestion/import/apply", json={"bundle": bundle})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["flagged_downgrade"] == 1

    with session_scope() as session:
        entry = session.query(ReferenceVersionEntry).filter_by(vendor="OpenSSH").one()
        assert entry.needs_review is True
        assert entry.min_version == "9.0"  # still applied, but flagged


def test_downgrade_with_confirmation_applies_cleanly(admin_client):
    with session_scope() as session:
        session.add(ReferenceVersionEntry(vendor="OpenSSH", type="router", min_version="9.5"))

    bundle = make_bundle(
        [
            {
                "model": None,
                "type": "router",
                "version": "9.0",
                "source": "x",
                "fetched_at": "x",
                "status": "ok",
            }
        ]
    )

    resp = admin_client.post(
        "/api/version-ingestion/import/apply",
        json={"bundle": bundle, "confirm_downgrade": True},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["flagged_downgrade"] == 0

    with session_scope() as session:
        entry = session.query(ReferenceVersionEntry).filter_by(vendor="OpenSSH").one()
        assert entry.needs_review is False


def test_apply_records_one_config_change_audit_with_no_secret(admin_client):
    bundle = make_bundle(
        [
            {
                "model": "portable",
                "type": "router",
                "version": "9.9",
                "source": "x",
                "fetched_at": "x",
                "status": "ok",
            }
        ]
    )
    admin_client.post("/api/version-ingestion/import/apply", json={"bundle": bundle})

    with session_scope() as session:
        events = (
            session.query(AuditLogEntry).filter_by(event_type=AuditEventType.CONFIG_CHANGE).all()
        )
        assert len(events) == 1
        detail = events[0].detail
        assert detail["action"] == "import"
        assert detail["vendor"] == "OpenSSH"
        assert KEY_HEX not in json.dumps(detail)


def test_tampered_bundle_is_rejected_no_write(admin_client):
    bundle = make_bundle(
        [
            {
                "model": "portable",
                "type": "router",
                "version": "9.9",
                "source": "x",
                "fetched_at": "x",
                "status": "ok",
            }
        ]
    )
    bundle["payload"]["entries"][0]["version"] = "99.99"  # tamper

    resp = admin_client.post("/api/version-ingestion/import/apply", json={"bundle": bundle})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "bundle_invalid"

    with session_scope() as session:
        assert session.query(ReferenceVersionEntry).count() == 0


def test_operator_gets_403_on_ingestion_endpoints(authed_client):
    bundle = make_bundle(
        [
            {
                "model": "portable",
                "type": "router",
                "version": "9.9",
                "source": "x",
                "fetched_at": "x",
                "status": "ok",
            }
        ]
    )
    assert authed_client.get("/api/version-ingestion/sources").status_code == 403
    assert (
        authed_client.post(
            "/api/version-ingestion/import/preview", json={"bundle": bundle}
        ).status_code
        == 403
    )
    assert (
        authed_client.post(
            "/api/version-ingestion/import/apply", json={"bundle": bundle}
        ).status_code
        == 403
    )


def test_source_crud_round_trip(admin_client):
    created = admin_client.post(
        "/api/version-ingestion/sources",
        json={
            "vendor": "OpenSSH",
            "source_url": "https://www.openssh.com/",
            "models": ["portable"],
        },
    )
    assert created.status_code == 201, created.text
    source_id = created.json()["id"]

    listed = admin_client.get("/api/version-ingestion/sources").json()
    assert any(s["id"] == source_id for s in listed)

    deleted = admin_client.delete(f"/api/version-ingestion/sources/{source_id}")
    assert deleted.status_code == 204

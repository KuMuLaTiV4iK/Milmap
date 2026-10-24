"""Contract tests for /api/reference-versions (FR-009-FR-011, V0.7):
threshold CRUD allowed for both Operator and Administrator (not
admin-gated), validation of `min_version`/required fields, and a
`CONFIG_CHANGE` audit event on each mutation."""
from asset_dashboard.db.base import session_scope
from asset_dashboard.db.models import AuditEventType, AuditLogEntry

ENTRY = {
    "vendor": "OpenSSH",
    "type": "router",
    "min_version": "9.0",
    "note": "Currently maintained",
}


def test_create_entry_as_operator_succeeds(authed_client):
    resp = authed_client.post("/api/reference-versions", json=ENTRY)
    assert resp.status_code == 201
    assert resp.json()["vendor"] == "OpenSSH"


def test_create_entry_as_administrator_succeeds(admin_client):
    resp = admin_client.post("/api/reference-versions", json=ENTRY)
    assert resp.status_code == 201


def test_create_entry_records_config_change_audit_event(authed_client):
    authed_client.post("/api/reference-versions", json=ENTRY)
    with session_scope() as session:
        events = (
            session.query(AuditLogEntry)
            .filter_by(event_type=AuditEventType.CONFIG_CHANGE)
            .all()
        )
        assert len(events) == 1
        assert events[0].detail["action"] == "create"


def test_create_entry_rejects_unparseable_min_version(authed_client):
    bad = dict(ENTRY, min_version="not-a-version")
    resp = authed_client.post("/api/reference-versions", json=bad)
    assert resp.status_code == 422


def test_create_entry_rejects_missing_required_fields(authed_client):
    bad = dict(ENTRY, vendor="")
    resp = authed_client.post("/api/reference-versions", json=bad)
    assert resp.status_code == 422


def test_create_entry_rejects_empty_type(authed_client):
    bad = dict(ENTRY, type="")
    resp = authed_client.post("/api/reference-versions", json=bad)
    assert resp.status_code == 422


def test_list_entries(authed_client):
    authed_client.post("/api/reference-versions", json=ENTRY)
    resp = authed_client.get("/api/reference-versions")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_update_entry(authed_client):
    created = authed_client.post("/api/reference-versions", json=ENTRY).json()
    updated = dict(ENTRY, note="Updated note")
    resp = authed_client.put(f"/api/reference-versions/{created['id']}", json=updated)
    assert resp.status_code == 200
    assert resp.json()["note"] == "Updated note"

    with session_scope() as session:
        events = (
            session.query(AuditLogEntry)
            .filter_by(event_type=AuditEventType.CONFIG_CHANGE)
            .all()
        )
        assert any(e.detail["action"] == "update" for e in events)


def test_update_nonexistent_entry_returns_404(authed_client):
    resp = authed_client.put("/api/reference-versions/does-not-exist", json=ENTRY)
    assert resp.status_code == 404


def test_delete_entry(authed_client):
    created = authed_client.post("/api/reference-versions", json=ENTRY).json()
    resp = authed_client.delete(f"/api/reference-versions/{created['id']}")
    assert resp.status_code == 204

    listed = authed_client.get("/api/reference-versions").json()
    assert listed == []


def test_delete_nonexistent_entry_returns_404(authed_client):
    resp = authed_client.delete("/api/reference-versions/does-not-exist")
    assert resp.status_code == 404


def test_reference_versions_routes_require_authentication(client):
    resp = client.get("/api/reference-versions")
    assert resp.status_code == 401

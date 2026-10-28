"""Threshold CRUD integration tests (FR-009-FR-011): create/edit/delete as
operator AND admin, each emits a CONFIG_CHANGE audit row, invalid
min_version is rejected."""

from asset_dashboard.db.base import session_scope
from asset_dashboard.db.models import AuditEventType, AuditLogEntry

ENTRY = {"vendor": "nginx", "type": "router", "min_version": "1.26"}


def test_create_threshold_as_operator_succeeds(authed_client):
    resp = authed_client.post("/api/reference-versions", json=ENTRY)
    assert resp.status_code == 201, resp.text
    assert resp.json()["min_version"] == "1.26"
    assert resp.json()["source"] == "manual"


def test_create_threshold_as_administrator_succeeds(admin_client):
    resp = admin_client.post("/api/reference-versions", json=ENTRY)
    assert resp.status_code == 201


def test_create_threshold_records_config_change_audit_event(authed_client):
    authed_client.post("/api/reference-versions", json=ENTRY)
    with session_scope() as session:
        events = (
            session.query(AuditLogEntry).filter_by(event_type=AuditEventType.CONFIG_CHANGE).all()
        )
        assert len(events) == 1
        assert events[0].detail["action"] == "create"


def test_create_threshold_rejects_missing_min_version(authed_client):
    bad = {"vendor": "nginx", "type": "router"}
    resp = authed_client.post("/api/reference-versions", json=bad)
    assert resp.status_code == 422


def test_create_threshold_rejects_empty_type(authed_client):
    bad = dict(ENTRY, type="")
    resp = authed_client.post("/api/reference-versions", json=bad)
    assert resp.status_code == 422


def test_create_threshold_accepts_a_free_form_type(authed_client):
    """`type` is classification text, not a fixed enum — real vendor
    catalogs need categories a small fixed list can't anticipate."""
    free_form = dict(ENTRY, type="UCM.Sys")
    resp = authed_client.post("/api/reference-versions", json=free_form)
    assert resp.status_code == 201, resp.text
    assert resp.json()["type"] == "UCM.Sys"


def test_create_threshold_rejects_unparseable_min_version(authed_client):
    bad = dict(ENTRY, min_version="not-a-version")
    resp = authed_client.post("/api/reference-versions", json=bad)
    assert resp.status_code == 422


def test_edit_threshold_flips_future_evaluation(authed_client):
    from asset_dashboard.compliance.version_check import check_version
    from asset_dashboard.db.base import session_scope as scope

    created = authed_client.post("/api/reference-versions", json=ENTRY).json()

    with scope() as session:
        result, _detail = check_version(session, "nginx 1.24")
    assert result == "non_compliant"

    update = authed_client.put(
        f"/api/reference-versions/{created['id']}",
        json={"vendor": "nginx", "type": "router", "min_version": "1.30"},
    )
    assert update.status_code == 200

    with scope() as session:
        result, _detail = check_version(session, "nginx 1.28")
    assert result == "non_compliant"  # now below the raised threshold

    with scope() as session:
        events = (
            session.query(AuditLogEntry).filter_by(event_type=AuditEventType.CONFIG_CHANGE).all()
        )
        assert any(e.detail["action"] == "update" for e in events)


def test_delete_threshold(authed_client):
    created = authed_client.post("/api/reference-versions", json=ENTRY).json()
    resp = authed_client.delete(f"/api/reference-versions/{created['id']}")
    assert resp.status_code == 204
    listed = authed_client.get("/api/reference-versions").json()
    assert listed == []

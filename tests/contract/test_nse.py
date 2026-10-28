"""Contract tests for /api/nse-scripts* (FR-010-FR-018)."""

PROFILE = {
    "name": "NSE test profile",
    "description": "",
    "target_scope": ["10.0.0.1"],
    "port_spec": "8291",
    "scan_params": {"timing": "T3"},
    "extracted_fields": [],
    "compliance_settings": {},
    "cache_freshness_seconds": 3600,
}


def test_any_authenticated_user_can_list_nse_scripts(authed_client):
    resp = authed_client.get("/api/nse-scripts")
    assert resp.status_code == 200


def test_operator_cannot_write_allowlist(authed_client):
    resp = authed_client.post("/api/nse-scripts", json={"script_id": "banner"})
    assert resp.status_code == 403


def test_admin_can_add_safe_script(admin_client):
    resp = admin_client.post("/api/nse-scripts", json={"script_id": "banner", "safety": "safe"})
    assert resp.status_code == 201
    assert "warning" not in resp.json()


def test_admin_adding_non_safe_script_gets_non_blocking_warning(admin_client):
    resp = admin_client.post(
        "/api/nse-scripts", json={"script_id": "some-intrusive-script", "safety": "other"}
    )
    assert resp.status_code == 201
    assert resp.json()["warning"] == "non_safe_script"


def test_duplicate_script_id_returns_422(admin_client):
    admin_client.post("/api/nse-scripts", json={"script_id": "banner"})
    resp = admin_client.post("/api/nse-scripts", json={"script_id": "banner"})
    assert resp.status_code == 422


def test_invalid_script_id_rejected(admin_client):
    resp = admin_client.post("/api/nse-scripts", json={"script_id": "Not Valid!!"})
    assert resp.status_code == 422


def test_profile_with_off_allowlist_script_rejected(authed_client):
    bad = dict(PROFILE, selected_scripts=["never-added"])
    resp = authed_client.post("/api/profiles", json=bad)
    assert resp.status_code == 422
    assert "selected_scripts" in resp.json()["error"]["fields"]


def test_bulk_import_is_admin_only(authed_client):
    resp = authed_client.post("/api/nse-scripts/import")
    assert resp.status_code == 403


def test_bulk_import_creates_entries_from_local_nmap_catalog(admin_client, tmp_path, monkeypatch):
    from asset_dashboard.config import settings as app_settings
    from asset_dashboard.db.base import session_scope
    from asset_dashboard.db.models import AuditEventType, AuditLogEntry

    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "script.db").write_text(
        'Entry { filename = "banner.nse", categories = { "safe", "discovery", } }\n'
    )
    monkeypatch.setattr(app_settings, "nmap_scripts_dir", scripts_dir)

    resp = admin_client.post("/api/nse-scripts/import")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["created"] == 1
    assert body["total_in_catalog"] == 1

    listed = admin_client.get("/api/nse-scripts").json()
    assert any(e["script_id"] == "banner" and e["safety"] == "safe" for e in listed)

    with session_scope() as session:
        events = (
            session.query(AuditLogEntry).filter_by(event_type=AuditEventType.ALLOWLIST_CHANGE).all()
        )
        assert any(e.detail.get("action") == "bulk_import" for e in events)


def test_bulk_import_returns_400_when_nmap_scripts_dir_not_found(
    admin_client, tmp_path, monkeypatch
):
    from asset_dashboard.config import settings as app_settings
    from asset_dashboard.nse import allowlist as allowlist_module

    monkeypatch.setattr(app_settings, "nmap_scripts_dir", tmp_path / "does-not-exist")
    # Block the PATH-based fallback too, so this is deterministic even on
    # a machine (like this one) that actually has nmap installed.
    monkeypatch.setattr(allowlist_module.shutil, "which", lambda *a, **k: None)
    resp = admin_client.post("/api/nse-scripts/import")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "nmap_scripts_not_found"


def test_removing_allowlist_entry_disables_the_profile_selection(admin_client):
    created = admin_client.post("/api/nse-scripts", json={"script_id": "banner"}).json()

    # A profile can select it while it is enabled.
    good = dict(PROFILE, selected_scripts=["banner"])
    profile = admin_client.post("/api/profiles", json=good).json()
    assert profile["selected_scripts"] == ["banner"]

    # Remove it from the allow-list.
    resp = admin_client.delete(f"/api/nse-scripts/{created['id']}")
    assert resp.status_code == 204

    # The same selection on a NEW save is now rejected (FR-013).
    resp2 = admin_client.put(
        f"/api/profiles/{profile['id']}",
        json=dict(good, version_token=profile["version_token"]),
    )
    assert resp2.status_code == 422

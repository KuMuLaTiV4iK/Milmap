"""Integration test for User Story 5: NSE scripts are offered through a
per-script control in the profile editor; selection persists across
save/reopen and appears in the command preview; a since-disabled script
still fails save validation (FR-016/FR-017). Presentation-only change —
persistence, allow-list validation and command composition unchanged.

Feature 009: the control is now a checkbox list (built client-side from
/api/nse-scripts) instead of a multi-select listbox."""

PROFILE = {
    "name": "NSE list control test",
    "description": "",
    "target_scope": ["10.0.0.1"],
    "port_spec": "8291",
    "scan_params": {"timing": "T3"},
    "extracted_fields": [],
    "selected_scripts": ["banner"],
    "compliance_settings": {},
    "cache_freshness_seconds": 3600,
}


def test_profile_editor_renders_a_checkbox_list_for_nse_scripts(authed_client, admin_client):
    admin_client.post("/api/nse-scripts", json={"script_id": "banner", "safety": "safe"})
    profile = authed_client.post("/api/profiles", json=PROFILE).json()

    page = authed_client.get(f"/profiles/{profile['id']}", headers={"accept": "text/html"})
    assert page.status_code == 200
    # The NSE control is now a checkbox-list container populated client-side.
    assert 'id="nse-scripts-list"' in page.text
    assert "checkbox-list" in page.text
    assert "nse-checkbox" in page.text  # the per-script checkbox class the JS builds


def test_selected_script_persists_across_save_and_reopen(authed_client, admin_client):
    admin_client.post("/api/nse-scripts", json={"script_id": "banner", "safety": "safe"})
    created = authed_client.post("/api/profiles", json=PROFILE).json()
    assert created["selected_scripts"] == ["banner"]

    reloaded = authed_client.get(f"/api/profiles/{created['id']}").json()
    assert reloaded["selected_scripts"] == ["banner"]


def test_selected_script_appears_in_command_preview(authed_client, admin_client):
    admin_client.post("/api/nse-scripts", json={"script_id": "banner", "safety": "safe"})
    resp = authed_client.post("/api/profiles/preview-command", json=PROFILE)
    assert resp.status_code == 200
    assert "banner" in resp.json()["display"]


def test_stale_disabled_script_selection_fails_save_validation(authed_client, admin_client):
    admin_client.post("/api/nse-scripts", json={"script_id": "banner", "safety": "safe"})
    created = authed_client.post("/api/profiles", json=PROFILE).json()

    # The script is later disabled on the allow-list.
    listed = admin_client.get("/api/nse-scripts").json()
    entry = next(e for e in listed if e["script_id"] == "banner")
    admin_client.put(f"/api/nse-scripts/{entry['id']}", json={"enabled": False})

    resp = authed_client.put(
        f"/api/profiles/{created['id']}",
        json=dict(PROFILE, version_token=created["version_token"]),
    )
    assert resp.status_code == 422
    assert "selected_scripts" in resp.json()["error"]["fields"]

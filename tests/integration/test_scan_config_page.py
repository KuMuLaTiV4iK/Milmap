"""Integration test for User Story 1 (feature 009): the Scan Configuration
page replaces the browser target prompt for every Run now.

- GET /profiles/{id}/scan renders the four editable fields pre-filled;
- a target-less profile cannot launch with an empty target (target_required);
- launching with edited timing/ports starts a run whose params reflect the
  edits while the saved profile is unchanged (SC-004);
- no Run-now entry point contains a window.prompt call (SC-005).
"""
from tests.contract.test_runs import _patch_successful_scan, _poll_until_finished

TARGETED_PROFILE = {
    "name": "Scan-config targeted",
    "description": "",
    "target_scope": ["10.10.0.0/24"],
    "port_spec": "5060-5062",
    "scan_params": {"timing": "T3"},
    "extracted_fields": ["open_ports", "service_version"],
    "compliance_settings": {"version_validity": True},
    "cache_freshness_seconds": 3600,
}

TARGET_LESS_PROFILE = dict(TARGETED_PROFILE, name="Scan-config target-less", target_scope=[])


def test_scan_page_renders_prefilled_fields(authed_client):
    profile = authed_client.post("/api/profiles", json=TARGETED_PROFILE).json()
    page = authed_client.get(f"/profiles/{profile['id']}/scan", headers={"accept": "text/html"})
    assert page.status_code == 200
    # Pre-filled target, port spec, and the Start Scan control are present.
    assert "10.10.0.0/24" in page.text
    assert "5060-5062" in page.text
    assert "Почати сканування" in page.text  # scan_config.start_scan


def test_scan_page_404_for_missing_profile(authed_client):
    resp = authed_client.get("/profiles/does-not-exist/scan", headers={"accept": "text/html"})
    assert resp.status_code == 404


def test_scan_page_targets_query_overrides_target_field(authed_client):
    profile = authed_client.post("/api/profiles", json=TARGETED_PROFILE).json()
    page = authed_client.get(
        f"/profiles/{profile['id']}/scan?targets=10.0.0.5,10.0.0.8",
        headers={"accept": "text/html"},
    )
    assert page.status_code == 200
    assert "10.0.0.5, 10.0.0.8" in page.text


def test_targetless_launch_without_target_is_rejected(authed_client):
    profile = authed_client.post("/api/profiles", json=TARGET_LESS_PROFILE).json()
    resp = authed_client.post(f"/api/profiles/{profile['id']}/runs", json={})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "target_required"


def test_launch_with_edited_params_reflects_edits_and_profile_unchanged(authed_client, monkeypatch):
    _patch_successful_scan(monkeypatch)
    profile = authed_client.post("/api/profiles", json=TARGETED_PROFILE).json()

    # The page would send only the changed fields; simulate that launch body.
    resp = authed_client.post(
        f"/api/profiles/{profile['id']}/runs",
        json={"scan_params": {"timing": "T4"}, "port_spec": "22,443"},
    )
    assert resp.status_code == 202
    run = _poll_until_finished(authed_client, resp.json()["run_id"])
    assert run["params_used"]["scan_params"]["timing"] == "T4"
    assert run["params_used"]["port_spec"] == "22,443"

    unchanged = authed_client.get(f"/api/profiles/{profile['id']}").json()
    assert unchanged["scan_params"]["timing"] == "T3"
    assert unchanged["port_spec"] == "5060-5062"


def test_no_browser_prompt_on_run_now_entry_points(authed_client):
    """SC-005: the prompt is gone from both Run-now entry points."""
    authed_client.post("/api/profiles", json=TARGETED_PROFILE)
    home = authed_client.get("/", headers={"accept": "text/html"})
    profiles = authed_client.get("/profiles", headers={"accept": "text/html"})
    assert "window.prompt" not in home.text
    assert "window.prompt" not in profiles.text
    # Run now now navigates to the scan page.
    assert "/scan" in profiles.text

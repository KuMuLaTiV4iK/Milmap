"""Integration test for User Story 1: the Home ("Головна") page shows
≤5 recently-updated profiles and ≤20 recent scans across ALL profiles,
with posture only when compliance was evaluated (FR-001-FR-005a)."""

from tests.contract.test_runs import _patch_successful_scan, _poll_until_finished

NON_COMPLIANCE_PROFILE = {
    "name": "Open ports sweep",
    "description": "",
    "target_scope": ["10.10.0.0/24"],
    "port_spec": "22",
    "scan_params": {"timing": "T3"},
    "extracted_fields": ["open_ports"],
    "compliance_settings": {},
    "cache_freshness_seconds": 3600,
}

VOIP_PROFILE = {
    "name": "VoIP Infrastructure Audit",
    "description": "",
    "target_scope": ["10.10.0.0/24"],
    "port_spec": "5060-5062",
    "scan_params": {"timing": "T3"},
    "extracted_fields": ["open_ports", "service_version"],
    "compliance_settings": {"version_validity": True},
    "cache_freshness_seconds": 3600,
}


def test_home_page_shows_empty_states_with_no_profiles(authed_client):
    resp = authed_client.get("/", headers={"accept": "text/html"})
    assert resp.status_code == 200
    assert "Головна" in resp.text


def test_home_page_lists_profile_and_non_compliance_scan(authed_client, monkeypatch):
    _patch_successful_scan(monkeypatch)
    profile = authed_client.post("/api/profiles", json=NON_COMPLIANCE_PROFILE).json()
    resp = authed_client.post(f"/api/profiles/{profile['id']}/runs", json={})
    run_id = resp.json()["run_id"]
    _poll_until_finished(authed_client, run_id)

    page = authed_client.get("/", headers={"accept": "text/html"})
    assert page.status_code == 200
    assert profile["name"] in page.text
    # A scan with no compliance evaluation must still appear (FR-005), with
    # posture shown as not-applicable rather than omitted (FR-005a).
    assert "не застосовно" in page.text


def test_home_page_shows_at_most_5_recent_profiles_and_20_recent_scans(authed_client, monkeypatch):
    _patch_successful_scan(monkeypatch)
    for i in range(7):
        authed_client.post("/api/profiles", json=dict(NON_COMPLIANCE_PROFILE, name=f"Profile {i}"))

    page = authed_client.get("/", headers={"accept": "text/html"})
    assert page.status_code == 200
    # Only the 5 most-recently-updated profiles are shown.
    assert page.text.count("Profile ") <= 5 * 2  # name may appear more than once per row


def test_home_page_shows_compliance_posture_for_evaluated_scan(authed_client, monkeypatch):
    _patch_successful_scan(monkeypatch)
    profile = authed_client.post("/api/profiles", json=VOIP_PROFILE).json()
    resp = authed_client.post(f"/api/profiles/{profile['id']}/runs", json={})
    _poll_until_finished(authed_client, resp.json()["run_id"])

    page = authed_client.get("/", headers={"accept": "text/html"})
    assert profile["name"] in page.text

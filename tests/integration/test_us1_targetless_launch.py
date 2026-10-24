"""Integration test for User Story 1: a target-less profile can be saved
and launched by supplying a target at launch time, from both the Home
page and the profiles list; the override is used for that run only
(FR-003a-FR-003d)."""
from tests.contract.test_runs import _patch_successful_scan, _poll_until_finished

TARGET_LESS_PROFILE = {
    "name": "Ad-hoc sweep",
    "description": "",
    "target_scope": [],
    "port_spec": "22",
    "scan_params": {"timing": "T3"},
    "extracted_fields": ["open_ports"],
    "compliance_settings": {},
    "cache_freshness_seconds": 3600,
}


def test_targetless_profile_saves_successfully(authed_client):
    resp = authed_client.post("/api/profiles", json=TARGET_LESS_PROFILE)
    assert resp.status_code == 201
    assert resp.json()["target_scope"] == []


def test_launch_targetless_profile_without_target_is_rejected(authed_client):
    profile = authed_client.post("/api/profiles", json=TARGET_LESS_PROFILE).json()
    resp = authed_client.post(f"/api/profiles/{profile['id']}/runs", json={})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "target_required"


def test_launch_targetless_profile_with_supplied_target_runs_and_profile_stays_targetless(
    authed_client, monkeypatch
):
    _patch_successful_scan(monkeypatch)
    profile = authed_client.post("/api/profiles", json=TARGET_LESS_PROFILE).json()

    resp = authed_client.post(
        f"/api/profiles/{profile['id']}/runs", json={"target_scope": ["10.10.0.5"]}
    )
    assert resp.status_code == 202
    run = _poll_until_finished(authed_client, resp.json()["run_id"])
    assert run["status"] == "completed"
    assert run["params_used"]["target_scope"] == ["10.10.0.5"]

    reloaded = authed_client.get(f"/api/profiles/{profile['id']}").json()
    assert reloaded["target_scope"] == []


def test_launch_targetless_profile_with_invalid_supplied_target_rejected(authed_client):
    profile = authed_client.post("/api/profiles", json=TARGET_LESS_PROFILE).json()
    resp = authed_client.post(
        f"/api/profiles/{profile['id']}/runs", json={"target_scope": ["garbage!!"]}
    )
    assert resp.status_code == 422


def test_home_page_shows_target_less_hint_for_targetless_profile(authed_client):
    authed_client.post("/api/profiles", json=TARGET_LESS_PROFILE)
    page = authed_client.get("/", headers={"accept": "text/html"})
    assert TARGET_LESS_PROFILE["name"] in page.text


def test_profiles_list_shows_target_less_hint_for_targetless_profile(authed_client):
    authed_client.post("/api/profiles", json=TARGET_LESS_PROFILE)
    page = authed_client.get("/profiles", headers={"accept": "text/html"})
    assert TARGET_LESS_PROFILE["name"] in page.text

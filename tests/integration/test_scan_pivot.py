"""Integration test for User Story 3 (feature 009): select hosts and scan them
with a chosen profile via the Scan Configuration page.

- /profiles/{id}/scan?targets=… pre-fills exactly those hosts (server-rendered);
- Start Scan creates a run whose effective target equals the shown hosts while
  the chosen profile's saved target is unchanged (SC-001, SC-004);
- a second launch of an already-running profile returns 409 already_running
  (FR-019).
"""
import threading

from asset_dashboard.discovery import nmap_runner
from tests.contract.test_runs import (
    SAMPLE_XML,
    _FakeProcess,
    _patch_successful_scan,
    _poll_until_finished,
)

PROFILE = {
    "name": "Scan-pivot target profile",
    "description": "",
    "target_scope": ["10.10.0.0/24"],
    "port_spec": "5060-5062",
    "scan_params": {"timing": "T3"},
    "extracted_fields": ["open_ports"],
    "compliance_settings": {},
    "cache_freshness_seconds": 3600,
}


def test_scan_page_prefills_pivoted_targets(authed_client):
    profile = authed_client.post("/api/profiles", json=PROFILE).json()
    page = authed_client.get(
        f"/profiles/{profile['id']}/scan?targets=10.10.0.5,10.10.0.8",
        headers={"accept": "text/html"},
    )
    assert page.status_code == 200
    assert "10.10.0.5, 10.10.0.8" in page.text
    # The profile's own saved target is not what's shown for the pivot.
    assert 'value="10.10.0.5, 10.10.0.8"' in page.text


def test_start_scan_targets_pivoted_hosts_profile_unchanged(authed_client, monkeypatch):
    _patch_successful_scan(monkeypatch)
    profile = authed_client.post("/api/profiles", json=PROFILE).json()

    # Start Scan sends the pivoted hosts as a target override.
    resp = authed_client.post(
        f"/api/profiles/{profile['id']}/runs",
        json={"target_scope": ["10.10.0.5", "10.10.0.8"]},
    )
    assert resp.status_code == 202
    run = _poll_until_finished(authed_client, resp.json()["run_id"])
    assert run["params_used"]["target_scope"] == ["10.10.0.5", "10.10.0.8"]

    # SC-004: the chosen profile's saved target is unchanged.
    unchanged = authed_client.get(f"/api/profiles/{profile['id']}").json()
    assert unchanged["target_scope"] == PROFILE["target_scope"]


def test_relaunch_of_running_profile_returns_409(authed_client, monkeypatch):
    hang = threading.Event()

    class _HangingProcess(_FakeProcess):
        def communicate(self):
            hang.wait(timeout=2.0)
            return self._stdout, self._stderr

    def fake_start_nmap(
        target_scope, port_spec, scan_params, extracted_fields=None, selected_scripts=None
    ):
        return nmap_runner.NmapRunHandle(
            process=_HangingProcess(stdout=SAMPLE_XML, returncode=0), command=["nmap"]
        )

    monkeypatch.setattr(nmap_runner, "start_nmap", fake_start_nmap)
    profile = authed_client.post("/api/profiles", json=PROFILE).json()

    first = authed_client.post(
        f"/api/profiles/{profile['id']}/runs", json={"target_scope": ["10.10.0.5"]}
    )
    assert first.status_code == 202

    second = authed_client.post(
        f"/api/profiles/{profile['id']}/runs", json={"target_scope": ["10.10.0.5"]}
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "already_running"

    # Release the first run and wait so its thread does not outlive the test.
    hang.set()
    _poll_until_finished(authed_client, first.json()["run_id"])

"""Integration test for User Story 4: historical runs + result caching.
See spec.md US4 Independent Test: run a profile twice in quick succession,
confirm the second is served from cache; confirm both are visible in
history with correct timestamps/profile/params."""

import time

from asset_dashboard.discovery import nmap_runner

PROFILE = {
    "name": "VoIP Infrastructure Audit",
    "description": "",
    "target_scope": ["10.10.0.0/24"],
    "port_spec": "5060-5062",
    "scan_params": {},
    "extracted_fields": ["open_ports", "service_version"],
    "compliance_settings": {},
    "cache_freshness_seconds": 3600,
    "host_links": [],
}

SAMPLE_XML = """<?xml version="1.0"?>
<nmaprun>
  <host><status state="up"/><address addr="10.10.0.5" addrtype="ipv4"/>
    <ports><port protocol="udp" portid="5060"><state state="open"/></port></ports>
  </host>
</nmaprun>
"""


class _FakeProcess:
    def __init__(self, stdout):
        self.stdout = stdout
        self.returncode = 0

    def communicate(self):
        return self.stdout, ""

    def poll(self):
        return self.returncode

    def terminate(self):
        pass


def _patch(monkeypatch):
    def fake_start_nmap(
        target_scope, port_spec, scan_params, extracted_fields=None, selected_scripts=None
    ):
        return nmap_runner.NmapRunHandle(process=_FakeProcess(SAMPLE_XML), command=["nmap"])

    monkeypatch.setattr(nmap_runner, "start_nmap", fake_start_nmap)


def _poll_until_finished(client, run_id, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        run = client.get(f"/api/runs/{run_id}").json()
        if run["status"] != "running":
            return run
        time.sleep(0.02)
    raise TimeoutError("run did not finish")


def test_run_twice_quick_succession_second_served_from_cache_both_in_history(
    authed_client, monkeypatch
):
    _patch(monkeypatch)
    profile = authed_client.post("/api/profiles", json=PROFILE).json()

    first_start = authed_client.post(f"/api/profiles/{profile['id']}/runs", json={})
    assert first_start.status_code == 202
    first = _poll_until_finished(authed_client, first_start.json()["run_id"])

    second_start = authed_client.post(f"/api/profiles/{profile['id']}/runs", json={})
    assert second_start.status_code == 200
    second = second_start.json()
    assert second["served_from_cache"] is True

    history = authed_client.get("/api/history").json()
    ids = {h["id"] for h in history}
    assert first["id"] in ids
    assert second["run_id"] in ids

    cached_entry = next(h for h in history if h["id"] == second["run_id"])
    assert cached_entry["served_from_cache"] is True
    assert cached_entry["params_used"] == first["params_used"]


def test_deleting_profile_retains_its_history(authed_client, monkeypatch):
    """FR-027 regression: deleting a profile must not fail or orphan-break
    its historical runs — they remain retrievable after deletion."""
    _patch(monkeypatch)
    profile = authed_client.post("/api/profiles", json=PROFILE).json()
    run_resp = authed_client.post(f"/api/profiles/{profile['id']}/runs", json={}).json()
    _poll_until_finished(authed_client, run_resp["run_id"])

    delete_resp = authed_client.delete(f"/api/profiles/{profile['id']}")
    assert delete_resp.status_code == 204

    # The run is still retrievable from history after the profile is gone.
    history = authed_client.get("/api/history").json()
    assert any(h["id"] == run_resp["run_id"] for h in history)

    detail = authed_client.get(f"/api/history/{run_resp['run_id']}").json()
    assert detail["run"]["profile_id"] is None  # FK set NULL, snapshot preserved
    assert detail["run"]["profile_snapshot"]["name"] == "VoIP Infrastructure Audit"

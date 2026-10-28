"""Contract tests for /api/history* and cache-hit vs force-fresh (FR-022-FR-026)."""

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


def _patch(monkeypatch, xml=SAMPLE_XML):
    def fake_start_nmap(
        target_scope, port_spec, scan_params, extracted_fields=None, selected_scripts=None
    ):
        return nmap_runner.NmapRunHandle(process=_FakeProcess(xml), command=["nmap"])

    monkeypatch.setattr(nmap_runner, "start_nmap", fake_start_nmap)


def _poll_until_finished(client, run_id, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        run = client.get(f"/api/runs/{run_id}").json()
        if run["status"] != "running":
            return run
        time.sleep(0.02)
    raise TimeoutError("run did not finish")


def test_history_lists_runs_newest_first(authed_client, monkeypatch):
    _patch(monkeypatch)
    profile = authed_client.post("/api/profiles", json=PROFILE).json()
    r1 = authed_client.post(f"/api/profiles/{profile['id']}/runs", json={}).json()
    _poll_until_finished(authed_client, r1["run_id"])

    history = authed_client.get("/api/history").json()
    assert len(history) == 1
    assert history[0]["id"] == r1["run_id"]
    assert history[0]["profile_name"] == "VoIP Infrastructure Audit"


def test_history_detail_returns_full_results(authed_client, monkeypatch):
    _patch(monkeypatch)
    profile = authed_client.post("/api/profiles", json=PROFILE).json()
    r1 = authed_client.post(f"/api/profiles/{profile['id']}/runs", json={}).json()
    _poll_until_finished(authed_client, r1["run_id"])

    detail = authed_client.get(f"/api/history/{r1['run_id']}").json()
    assert detail["run"]["status"] == "completed"
    assert len(detail["results"]) == 1


def test_second_run_within_freshness_window_is_served_from_cache(authed_client, monkeypatch):
    _patch(monkeypatch)
    profile = authed_client.post("/api/profiles", json=PROFILE).json()

    first = authed_client.post(f"/api/profiles/{profile['id']}/runs", json={}).json()
    _poll_until_finished(authed_client, first["run_id"])

    second_resp = authed_client.post(f"/api/profiles/{profile['id']}/runs", json={})
    assert second_resp.status_code == 200  # cache hit, not 202
    second = second_resp.json()
    assert second["served_from_cache"] is True
    assert second["source_run_id"] == first["run_id"]
    assert second["status"] == "completed"

    # Cached run's results are a labelled copy, not a fresh scan.
    results = authed_client.get(f"/api/runs/{second['run_id']}/results").json()
    assert len(results) == 1


def test_force_fresh_bypasses_cache(authed_client, monkeypatch):
    _patch(monkeypatch)
    profile = authed_client.post("/api/profiles", json=PROFILE).json()

    first = authed_client.post(f"/api/profiles/{profile['id']}/runs", json={}).json()
    _poll_until_finished(authed_client, first["run_id"])

    forced_resp = authed_client.post(
        f"/api/profiles/{profile['id']}/runs", json={"force_fresh": True}
    )
    assert forced_resp.status_code == 202  # a genuinely new run, not a cache hit
    forced = _poll_until_finished(authed_client, forced_resp.json()["run_id"])
    assert forced["served_from_cache"] is False


def test_history_routes_require_authentication(client):
    resp = client.get("/api/history")
    assert resp.status_code == 401

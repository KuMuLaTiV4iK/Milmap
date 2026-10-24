"""Integration test for User Story 2: full operator control over the scan
command (see spec.md US2 Independent Test): toggle each extraction option
independently (incl. open-ports-only) and change timing; save/run; the
preview matches selections exactly and -sV appears only when version
extraction is on."""
import time

from asset_dashboard.discovery import nmap_runner

OPEN_PORTS_ONLY_PROFILE = {
    "name": "Open ports only sweep",
    "description": "",
    "target_scope": ["10.0.0.0/24"],
    "port_spec": "1-1024",
    "scan_params": {},
    "extracted_fields": ["open_ports"],
    "compliance_settings": {},
    "cache_freshness_seconds": 3600,
}

SAMPLE_XML = """<?xml version="1.0"?>
<nmaprun>
  <host><status state="up"/><address addr="10.0.0.5" addrtype="ipv4"/>
    <ports><port protocol="tcp" portid="22"><state state="open"/></port></ports>
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


def _poll_until_finished(client, run_id, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        run = client.get(f"/api/runs/{run_id}").json()
        if run["status"] != "running":
            return run
        time.sleep(0.02)
    raise TimeoutError("run did not finish")


def test_new_profile_timing_defaults_to_t3(authed_client):
    page = authed_client.get("/profiles/new")
    assert page.status_code == 200
    assert 'value="T3" selected' in page.text


def test_open_ports_only_profile_saves_and_runs_without_version_data(authed_client, monkeypatch):
    def fake_start_nmap(
        target_scope, port_spec, scan_params, extracted_fields=None, selected_scripts=None
    ):
        assert "-sV" not in nmap_runner.build_nmap_command(
            target_scope, port_spec, scan_params, extracted_fields, selected_scripts
        )
        return nmap_runner.NmapRunHandle(process=_FakeProcess(SAMPLE_XML), command=["nmap"])

    monkeypatch.setattr(nmap_runner, "start_nmap", fake_start_nmap)

    created = authed_client.post("/api/profiles", json=OPEN_PORTS_ONLY_PROFILE).json()
    assert created["extracted_fields"] == ["open_ports"]

    start = authed_client.post(f"/api/profiles/{created['id']}/runs", json={})
    assert start.status_code == 202
    run = _poll_until_finished(authed_client, start.json()["run_id"])
    assert run["status"] == "completed"

    results = authed_client.get(f"/api/runs/{run['id']}/results").json()
    assert results[0]["extracted"]["service_version"] is None


def test_preview_matches_selections_exactly(authed_client):
    resp = authed_client.post("/api/profiles/preview-command", json=OPEN_PORTS_ONLY_PROFILE)
    assert resp.status_code == 200
    body = resp.json()
    assert "-sV" not in body["command"]
    assert "-T3" in body["command"]  # default applied in preview too

    with_version = dict(OPEN_PORTS_ONLY_PROFILE, extracted_fields=["open_ports", "service_version"])
    resp2 = authed_client.post("/api/profiles/preview-command", json=with_version)
    assert "-sV" in resp2.json()["command"]

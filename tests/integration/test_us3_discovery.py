"""Integration test for feature-001 User Story 3: run a profile and review
results.

Feature 002 (FR-004) removes the host-management-link capability from
profiles and the UI entirely (deferred to a later standalone function):
`management_link` is never populated by the runner and never rendered in
the run-detail page, even if a legacy `host_links` payload is still sent.
"""
import time

from asset_dashboard.discovery import nmap_runner

VOIP_PROFILE = {
    "name": "VoIP Infrastructure Audit",
    "description": "",
    "target_scope": ["10.10.0.0/24"],
    "port_spec": "5060-5062",
    "scan_params": {"timing": "T3"},
    "extracted_fields": ["open_ports", "service_version"],
    "compliance_settings": {},
    "cache_freshness_seconds": 3600,
}

SAMPLE_XML = """<?xml version="1.0"?>
<nmaprun>
  <host>
    <status state="up"/>
    <address addr="10.10.0.5" addrtype="ipv4"/>
    <ports>
      <port protocol="udp" portid="5060">
        <state state="open"/>
        <service name="sip" product="Asterisk PBX" version="16.2.1"/>
      </port>
    </ports>
  </host>
  <host>
    <status state="up"/>
    <address addr="10.10.0.6" addrtype="ipv4"/>
    <ports><port protocol="udp" portid="5061"><state state="open"/></port></ports>
  </host>
</nmaprun>
"""


def _poll_until_finished(client, run_id, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        run = client.get(f"/api/runs/{run_id}").json()
        if run["status"] != "running":
            return run
        time.sleep(0.02)
    raise TimeoutError(f"run {run_id} did not finish within {timeout}s")


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


def test_run_profile_and_review_results(authed_client, monkeypatch):
    def fake_start_nmap(
        target_scope, port_spec, scan_params, extracted_fields=None, selected_scripts=None
    ):
        return nmap_runner.NmapRunHandle(process=_FakeProcess(SAMPLE_XML), command=["nmap"])

    monkeypatch.setattr(nmap_runner, "start_nmap", fake_start_nmap)

    profile = authed_client.post("/api/profiles", json=VOIP_PROFILE).json()
    start = authed_client.post(f"/api/profiles/{profile['id']}/runs", json={})
    assert start.status_code == 202
    run_id = start.json()["run_id"]

    run = _poll_until_finished(authed_client, run_id)
    assert run["status"] == "completed"
    assert run["summary"]["hosts"] == 2

    results = authed_client.get(f"/api/runs/{run_id}/results").json()
    addresses = {r["address"] for r in results}
    assert addresses == {"10.10.0.5", "10.10.0.6"}

    page = authed_client.get(f"/runs/{run_id}")
    assert page.status_code == 200
    assert "10.10.0.5" in page.text


def test_management_link_removed_even_with_legacy_host_links_payload(authed_client, monkeypatch):
    def fake_start_nmap(
        target_scope, port_spec, scan_params, extracted_fields=None, selected_scripts=None
    ):
        return nmap_runner.NmapRunHandle(process=_FakeProcess(SAMPLE_XML), command=["nmap"])

    monkeypatch.setattr(nmap_runner, "start_nmap", fake_start_nmap)

    legacy_profile = dict(VOIP_PROFILE, name="Legacy host_links payload")
    legacy_profile["host_links"] = [{"label": "Manage", "url_template": "https://{host}/"}]
    profile = authed_client.post("/api/profiles", json=legacy_profile).json()
    assert "host_links" not in profile

    start = authed_client.post(f"/api/profiles/{profile['id']}/runs", json={})
    run_id = start.json()["run_id"]
    _poll_until_finished(authed_client, run_id)

    results = authed_client.get(f"/api/runs/{run_id}/results").json()
    assert all(r["management_link"] is None for r in results)

    page = authed_client.get(f"/runs/{run_id}")
    assert "https://10.10.0.5/" not in page.text

"""Integration test: "Schedule this scan" from Home / History / a run's results.

The button is a link to /schedules?from_run=<run_id>; the schedules page then
pre-fills the create form with that run's profile and scanned target (leaving
the recurrence for the operator). Replaces the earlier seconds-prompt popup."""
import time

from asset_dashboard.discovery import nmap_runner

PROFILE = {
    "name": "Mikrotik version",
    "description": "",
    "target_scope": ["192.168.1.3"],
    "port_spec": "8291",
    "scan_params": {},
    "extracted_fields": ["open_ports", "service_version"],
    "compliance_settings": {},
    "cache_freshness_seconds": 3600,
    "host_links": [],
}

SAMPLE_XML = """<?xml version="1.0"?>
<nmaprun>
  <host><status state="up"/><address addr="192.168.1.3" addrtype="ipv4"/><ports/></host>
</nmaprun>
"""


class _FakeProcess:
    returncode = 0

    def communicate(self):
        return SAMPLE_XML, ""

    def poll(self):
        return self.returncode

    def terminate(self):
        pass


def _patch(monkeypatch):
    def fake_start_nmap(
        target_scope, port_spec, scan_params, extracted_fields=None, selected_scripts=None
    ):
        return nmap_runner.NmapRunHandle(process=_FakeProcess(), command=["nmap"])

    monkeypatch.setattr(nmap_runner, "start_nmap", fake_start_nmap)


def _completed_run(client, monkeypatch):
    _patch(monkeypatch)
    profile = client.post("/api/profiles", json=PROFILE).json()
    run_id = client.post(f"/api/profiles/{profile['id']}/runs", json={}).json()["run_id"]
    deadline = time.time() + 3.0
    while time.time() < deadline:
        if client.get(f"/api/runs/{run_id}").json()["status"] != "running":
            break
        time.sleep(0.02)
    return profile, run_id


def test_history_and_run_pages_link_to_schedule_prefill(authed_client, monkeypatch):
    profile, run_id = _completed_run(authed_client, monkeypatch)

    link = f"/schedules?from_run={run_id}"
    assert link in authed_client.get("/history").text
    assert link in authed_client.get("/").text          # Home / dashboard recent scans
    assert link in authed_client.get(f"/runs/{run_id}").text

    # The old seconds-prompt handler is gone.
    assert "Recurrence interval in seconds" not in authed_client.get("/history").text


def test_schedules_page_prefills_profile_and_target_from_run(authed_client, monkeypatch):
    profile, run_id = _completed_run(authed_client, monkeypatch)

    html = authed_client.get(f"/schedules?from_run={run_id}").text
    # The server embeds the resolved prefill for the form to apply.
    assert profile["id"] in html
    assert "192.168.1.3" in html
    assert "prefill" in html


def test_schedules_page_without_from_run_has_no_prefill(authed_client):
    html = authed_client.get("/schedules").text
    assert "const prefill = null" in html

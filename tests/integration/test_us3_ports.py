"""Integration test for User Story 3: the ports column adapts to scan
size — a small scan (<=10 distinct ports) shows every port with its
state, a large scan shows open-only, a large scan with no open ports
shows the "all closed/filtered" placeholder (FR-009-FR-011).

Uses the real captured nmap output in debug/1_prof_output.txt (2
distinct ports: 22/tcp, 8291/tcp -> small-scan mode)."""

from pathlib import Path

from asset_dashboard.discovery import nmap_runner
from tests.contract.test_runs import _poll_until_finished

FIXTURE_XML = (
    (Path(__file__).resolve().parents[2] / "debug" / "1_prof_output.txt")
    .read_text(encoding="utf-8")
    .split("\n", 1)[1]
)  # drop the leading `nmap ...` command-line comment

PROFILE = {
    "name": "Mikrotik sweep",
    "description": "",
    "target_scope": ["192.168.1.0/24"],
    "port_spec": "22,8291",
    "scan_params": {"timing": "T3"},
    "extracted_fields": ["open_ports", "service_version"],
    "compliance_settings": {},
    "cache_freshness_seconds": 3600,
}


class _FakeProcess:
    def __init__(self, xml):
        self._xml = xml
        self.returncode = 0

    def communicate(self):
        return self._xml, ""

    def poll(self):
        return self.returncode

    def terminate(self):
        pass


def _patch_fixture_scan(monkeypatch):
    def fake_start_nmap(
        target_scope, port_spec, scan_params, extracted_fields=None, selected_scripts=None
    ):
        return nmap_runner.NmapRunHandle(process=_FakeProcess(FIXTURE_XML), command=["nmap"])

    monkeypatch.setattr(nmap_runner, "start_nmap", fake_start_nmap)


def test_small_scan_shows_open_and_filtered_ports_distinctly(authed_client, monkeypatch):
    _patch_fixture_scan(monkeypatch)
    profile = authed_client.post("/api/profiles", json=PROFILE).json()
    resp = authed_client.post(f"/api/profiles/{profile['id']}/runs", json={})
    run = _poll_until_finished(authed_client, resp.json()["run_id"])
    assert run["status"] == "completed"
    assert run["summary"]["ports_in_results"] == 2

    results = authed_client.get(f"/api/runs/{run['id']}/results").json()
    host = next(r for r in results if r["address"] == "192.168.1.1")
    ports_by_number = {p["port"]: p["state"] for p in host["open_ports"]}
    assert ports_by_number == {22: "open", 8291: "filtered"}

    page = authed_client.get(f"/runs/{run['id']}", headers={"accept": "text/html"})
    assert page.status_code == 200
    assert "22/tcp" in page.text
    assert "8291/tcp" in page.text
    # A filtered port must never render as open.
    assert "filtered" in page.text


def test_large_scan_shows_open_only_and_all_closed_placeholder(authed_client, monkeypatch):
    many_ports_open_host = "".join(
        f'<port protocol="tcp" portid="{p}"><state state="open"/><service name="svc"/></port>'
        for p in range(1, 12)
    )
    many_ports_closed_host = "".join(
        f'<port protocol="tcp" portid="{p}"><state state="closed"/><service name="svc"/></port>'
        for p in range(1, 12)
    )
    xml = f"""<?xml version="1.0"?>
<nmaprun>
  <host><status state="up"/><address addr="10.0.0.1" addrtype="ipv4"/>
    <ports>{many_ports_open_host}</ports>
  </host>
  <host><status state="up"/><address addr="10.0.0.2" addrtype="ipv4"/>
    <ports>{many_ports_closed_host}</ports>
  </host>
</nmaprun>
"""

    def fake_start_nmap(
        target_scope, port_spec, scan_params, extracted_fields=None, selected_scripts=None
    ):
        return nmap_runner.NmapRunHandle(process=_FakeProcess(xml), command=["nmap"])

    monkeypatch.setattr(nmap_runner, "start_nmap", fake_start_nmap)

    profile = authed_client.post(
        "/api/profiles", json=dict(PROFILE, name="Large scan", port_spec="1-11")
    ).json()
    resp = authed_client.post(f"/api/profiles/{profile['id']}/runs", json={})
    run = _poll_until_finished(authed_client, resp.json()["run_id"])
    assert run["summary"]["ports_in_results"] == 11

    page = authed_client.get(f"/runs/{run['id']}", headers={"accept": "text/html"})
    assert "Всі порти closed або filtered" in page.text

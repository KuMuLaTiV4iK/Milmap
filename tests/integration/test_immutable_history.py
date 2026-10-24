"""FR-012a, SC-009: a finding's `checked_version`/`threshold` are frozen at
scan time. Raising a threshold afterward never rewrites a historical
finding; only a new scan reflects the new threshold."""
import time

from asset_dashboard.db.base import session_scope
from asset_dashboard.db.models import ReferenceVersionEntry
from asset_dashboard.discovery import nmap_runner

PROFILE = {
    "name": "SSH immutable history",
    "description": "",
    "target_scope": ["10.10.0.0/24"],
    "port_spec": "22",
    "scan_params": {"timing": "T3"},
    "extracted_fields": ["open_ports", "service_version"],
    "compliance_settings": {"version_validity": True},
    "cache_freshness_seconds": 3600,
}

SAMPLE_XML = """<?xml version="1.0"?>
<nmaprun>
  <host>
    <status state="up"/>
    <address addr="10.10.0.7" addrtype="ipv4"/>
    <ports>
      <port protocol="tcp" portid="22">
        <state state="open"/>
        <service name="ssh" product="OpenSSH" version="9.2"/>
      </port>
    </ports>
  </host>
</nmaprun>
"""


class _FakeProcess:
    def __init__(self):
        self.returncode = 0

    def communicate(self):
        return SAMPLE_XML, ""

    def poll(self):
        return self.returncode

    def terminate(self):
        pass


def _poll_until_finished(client, run_id, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        run = client.get(f"/api/runs/{run_id}").json()
        if run["status"] != "running":
            return run
        time.sleep(0.02)
    raise TimeoutError("run did not finish")


def test_raising_threshold_does_not_rewrite_historical_finding(authed_client, monkeypatch):
    with session_scope() as session:
        session.add(
            ReferenceVersionEntry(vendor="OpenSSH", type="router", min_version="9.0")
        )

    def fake_start_nmap(
        target_scope, port_spec, scan_params, extracted_fields=None, selected_scripts=None
    ):
        return nmap_runner.NmapRunHandle(process=_FakeProcess(), command=["nmap"])

    monkeypatch.setattr(nmap_runner, "start_nmap", fake_start_nmap)

    profile = authed_client.post("/api/profiles", json=PROFILE).json()
    start = authed_client.post(f"/api/profiles/{profile['id']}/runs", json={})
    run = _poll_until_finished(authed_client, start.json()["run_id"])
    assert run["status"] == "completed"

    results = authed_client.get(f"/api/runs/{run['id']}/results").json()
    finding = next(f for f in results[0]["findings"] if f["control"] == "version_validity")
    assert finding["result"] == "compliant"
    assert finding["detail"]["checked_version"] == "9.2"
    assert finding["detail"]["threshold"] == "9.0"

    # Raise the threshold above the detected version.
    with session_scope() as session:
        entry = session.query(ReferenceVersionEntry).filter_by(vendor="OpenSSH").one()
        entry.min_version = "9.5"

    # The historical run's persisted finding is unchanged.
    reopened = authed_client.get(f"/api/runs/{run['id']}/results").json()
    reopened_finding = next(
        f for f in reopened[0]["findings"] if f["control"] == "version_validity"
    )
    assert reopened_finding["result"] == "compliant"
    assert reopened_finding["detail"]["threshold"] == "9.0"

"""Integration test for User Story 6: compliance auditing end-to-end
through the real discovery pipeline (see spec.md US6 Independent Test):
run the "VoIP Infrastructure Audit" profile and confirm firmware version
is evaluated offline and flagged valid/invalid/unknown.

Feature 002 (FR-020): the default-credential check is decoupled from
discovery-profile runs — it is now the standalone tool exercised in
tests/integration/test_us5_credential_tool.py. This test asserts the
negative: running a profile does NOT produce a default_credentials
finding, even when a legacy `compliance_settings.default_credentials`
payload is still sent.

`nmap` is mocked (no real network device is available in this
environment).
"""
import time

from asset_dashboard.db.base import session_scope
from asset_dashboard.db.models import ReferenceVersionEntry
from asset_dashboard.discovery import nmap_runner

VOIP_PROFILE = {
    "name": "VoIP Infrastructure Audit",
    "description": "",
    "target_scope": ["10.10.0.0/24"],
    "port_spec": "5060-5062",
    "scan_params": {"timing": "T3"},
    "extracted_fields": ["open_ports", "service_version"],
    "compliance_settings": {"version_validity": True, "default_credentials": True},
    "cache_freshness_seconds": 3600,
}

# Two hosts: one on an EOL/vulnerable Asterisk build with default creds
# still active, one on a current build with hardened creds.
TWO_HOST_XML = """<?xml version="1.0"?>
<nmaprun>
  <host><status state="up"/><address addr="10.10.0.5" addrtype="ipv4"/>
    <ports><port protocol="udp" portid="5060"><state state="open"/>
      <service name="sip" product="Asterisk PBX" version="16.2.1"/>
    </port></ports>
  </host>
  <host><status state="up"/><address addr="10.10.0.6" addrtype="ipv4"/>
    <ports><port protocol="udp" portid="5060"><state state="open"/>
      <service name="sip" product="Asterisk PBX" version="20.5"/>
    </port></ports>
  </host>
  <host><status state="up"/><address addr="10.10.0.7" addrtype="ipv4"/>
    <ports><port protocol="udp" portid="5060"><state state="open"/>
      <service name="sip" product="Unknown Vendor" version="1.0"/>
    </port></ports>
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


def _poll_until_finished(client, run_id, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        run = client.get(f"/api/runs/{run_id}").json()
        if run["status"] != "running":
            return run
        time.sleep(0.02)
    raise TimeoutError("run did not finish")


def test_voip_audit_version_validity_without_default_credentials(authed_client, monkeypatch):
    def fake_start_nmap(
        target_scope, port_spec, scan_params, extracted_fields=None, selected_scripts=None
    ):
        return nmap_runner.NmapRunHandle(process=_FakeProcess(TWO_HOST_XML), command=["nmap"])

    monkeypatch.setattr(nmap_runner, "start_nmap", fake_start_nmap)

    # Seed the offline version-validity dataset.
    with session_scope() as session:
        session.add(
            ReferenceVersionEntry(
                vendor="Asterisk", type="ucm", min_version="20.0", note=None,
            )
        )

    profile = authed_client.post("/api/profiles", json=VOIP_PROFILE).json()
    start = authed_client.post(f"/api/profiles/{profile['id']}/runs", json={})
    assert start.status_code == 202
    run = _poll_until_finished(authed_client, start.json()["run_id"])
    assert run["status"] == "completed"

    results = authed_client.get(f"/api/runs/{run['id']}/results").json()
    by_address = {r["address"]: r for r in results}

    # --- Version validity (FR-034, FR-035) ---
    version_findings = {
        addr: next(f for f in r["findings"] if f["control"] == "version_validity")
        for addr, r in by_address.items()
    }
    assert version_findings["10.10.0.5"]["result"] == "non_compliant"  # EOL 16.2.1 -> invalid
    assert version_findings["10.10.0.6"]["result"] == "compliant"  # 20.x -> valid
    assert version_findings["10.10.0.7"]["result"] == "unknown"  # not in reference dataset

    # --- FR-020: a discovery-profile run NEVER performs the default-credential
    # check, even though this profile's legacy payload still sets
    # compliance_settings.default_credentials — it is a standalone tool now
    # (see test_us5_credential_tool.py).
    for r in results:
        assert all(f["control"] != "default_credentials" for f in r["findings"])

    # --- Dashboard-level posture check (SC-011): reviewable without re-scanning ---
    history_detail = authed_client.get(f"/api/history/{run['id']}").json()
    assert len(history_detail["results"]) == 3


def test_dashboard_shows_last_run_compliance_posture(authed_client, monkeypatch):
    def fake_start_nmap(
        target_scope, port_spec, scan_params, extracted_fields=None, selected_scripts=None
    ):
        return nmap_runner.NmapRunHandle(process=_FakeProcess(TWO_HOST_XML), command=["nmap"])

    monkeypatch.setattr(nmap_runner, "start_nmap", fake_start_nmap)

    profile = authed_client.post("/api/profiles", json=VOIP_PROFILE).json()
    start = authed_client.post(f"/api/profiles/{profile['id']}/runs", json={})
    _poll_until_finished(authed_client, start.json()["run_id"])

    page = authed_client.get("/")
    assert page.status_code == 200
    assert "VoIP Infrastructure Audit" in page.text

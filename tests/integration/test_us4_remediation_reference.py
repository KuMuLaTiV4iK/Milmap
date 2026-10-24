"""Integration test for User Story 4: a non-compliant row is
orange-highlighted and shows the expected valid version/note, and the
reference-versions view lists entries and is editable (FR-012-FR-015b)."""
from asset_dashboard.db.base import session_scope
from asset_dashboard.db.models import ReferenceVersionEntry
from asset_dashboard.discovery import nmap_runner
from tests.contract.test_runs import _poll_until_finished

PROFILE = {
    "name": "SSH compliance sweep",
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
        <service name="ssh" product="OpenSSH" version="7.4"/>
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


def test_non_compliant_row_orange_and_shows_expected_valid_version(authed_client, monkeypatch):
    with session_scope() as session:
        session.add(
            ReferenceVersionEntry(
                vendor="OpenSSH", type="router", min_version="9.0",
                note="End-of-life",
            )
        )

    def fake_start_nmap(
        target_scope, port_spec, scan_params, extracted_fields=None, selected_scripts=None
    ):
        return nmap_runner.NmapRunHandle(process=_FakeProcess(), command=["nmap"])

    monkeypatch.setattr(nmap_runner, "start_nmap", fake_start_nmap)

    profile = authed_client.post("/api/profiles", json=PROFILE).json()
    resp = authed_client.post(f"/api/profiles/{profile['id']}/runs", json={})
    run = _poll_until_finished(authed_client, resp.json()["run_id"])
    assert run["status"] == "completed"

    page = authed_client.get(f"/runs/{run['id']}", headers={"accept": "text/html"})
    assert page.status_code == 200
    assert "row-non-compliant" in page.text
    assert "OpenSSH 9.0" in page.text
    assert "End-of-life" in page.text


def test_reference_versions_page_lists_and_allows_edit(authed_client):
    created = authed_client.post(
        "/api/reference-versions",
        json={
            "vendor": "OpenSSH",
            "type": "router",
            "min_version": "9.0",
        },
    ).json()

    # Feature 006 (FR-013a): the version dictionary now lives inside the
    # Configuration page; the old standalone URL redirects there, and the
    # dictionary card is rendered on Configuration (its rows load via the
    # operator-accessible API, exercised below and in test_authz.py).
    redirect = authed_client.get("/reference-versions", follow_redirects=False)
    assert redirect.status_code in (302, 307)
    assert redirect.headers["location"] == "/configuration"

    config_page = authed_client.get("/configuration", headers={"accept": "text/html"})
    assert config_page.status_code == 200
    assert "reference-versions-card" in config_page.text

    listed = authed_client.get("/api/reference-versions").json()
    assert any(e["vendor"] == "OpenSSH" and e["min_version"] == "9.0" for e in listed)

    update = authed_client.put(
        f"/api/reference-versions/{created['id']}",
        json={
            "vendor": "OpenSSH",
            "type": "router",
            "min_version": "9.0",
            "note": "Current stable branch",
        },
    )
    assert update.status_code == 200


def test_reference_versions_editable_by_administrator_too(admin_client):
    resp = admin_client.post(
        "/api/reference-versions",
        json={
            "vendor": "Cisco",
            "type": "router",
            "min_version": "15.0",
        },
    )
    assert resp.status_code == 201

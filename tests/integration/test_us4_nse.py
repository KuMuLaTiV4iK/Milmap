"""Integration test for User Story 4: select NSE scripts; manage the
allow-list in Configuration (see spec.md US4 Independent Test): admin adds
a script in Configuration -> it appears in the profile checklist -> a
profile applying it runs with --script; removing it disables the
selection."""

import time

from asset_dashboard.discovery import nmap_runner

PROFILE = {
    "name": "MikroTik sweep",
    "description": "",
    "target_scope": ["10.0.0.1"],
    "port_spec": "8291",
    "scan_params": {"timing": "T3"},
    "extracted_fields": [],
    "compliance_settings": {},
    "cache_freshness_seconds": 3600,
}

SAMPLE_XML = """<?xml version="1.0"?>
<nmaprun>
  <host><status state="up"/><address addr="10.0.0.1" addrtype="ipv4"/>
    <ports><port protocol="tcp" portid="8291">
      <state state="open"/>
      <script id="mikrotik-routeros-version" output="RouterOS 7.1"/>
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


def _poll_until_finished(client, run_id, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        run = client.get(f"/api/runs/{run_id}").json()
        if run["status"] != "running":
            return run
        time.sleep(0.02)
    raise TimeoutError("run did not finish")


def test_add_script_appears_in_checklist_runs_with_script_flag_captures_output(
    admin_client, monkeypatch
):
    added = admin_client.post(
        "/api/nse-scripts",
        json={"script_id": "mikrotik-routeros-version", "expected_ports": [8291]},
    )
    assert added.status_code == 201

    checklist = admin_client.get("/api/nse-scripts").json()
    assert any(s["script_id"] == "mikrotik-routeros-version" for s in checklist)

    captured_commands = []

    def fake_start_nmap(
        target_scope, port_spec, scan_params, extracted_fields=None, selected_scripts=None
    ):
        cmd = nmap_runner.build_nmap_command(
            target_scope, port_spec, scan_params, extracted_fields, selected_scripts
        )
        captured_commands.append(cmd)
        return nmap_runner.NmapRunHandle(process=_FakeProcess(SAMPLE_XML), command=cmd)

    monkeypatch.setattr(nmap_runner, "start_nmap", fake_start_nmap)

    profile = admin_client.post(
        "/api/profiles", json=dict(PROFILE, selected_scripts=["mikrotik-routeros-version"])
    ).json()
    start = admin_client.post(f"/api/profiles/{profile['id']}/runs", json={})
    assert start.status_code == 202
    run = _poll_until_finished(admin_client, start.json()["run_id"])
    assert run["status"] == "completed"

    assert "--script" in captured_commands[0]
    assert "mikrotik-routeros-version" in captured_commands[0]

    results = admin_client.get(f"/api/runs/{run['id']}/results").json()
    assert results[0]["extracted"]["nse"]["mikrotik-routeros-version"] == "RouterOS 7.1"


def test_removing_script_from_allowlist_disables_selection(admin_client):
    entry = admin_client.post("/api/nse-scripts", json={"script_id": "banner"}).json()
    profile = admin_client.post(
        "/api/profiles", json=dict(PROFILE, name="Banner sweep", selected_scripts=["banner"])
    ).json()

    admin_client.delete(f"/api/nse-scripts/{entry['id']}")

    # Re-saving the profile with the now-removed script is rejected.
    resp = admin_client.put(
        f"/api/profiles/{profile['id']}",
        json=dict(
            PROFILE,
            name="Banner sweep",
            selected_scripts=["banner"],
            version_token=profile["version_token"],
        ),
    )
    assert resp.status_code == 422

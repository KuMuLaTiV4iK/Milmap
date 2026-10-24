"""Contract tests for the feature-009 one-off per-run overrides on
POST /api/profiles/{id}/runs (port_spec / scan_params / extracted_fields).

Like test_runs.py, `nmap` is not installed in this environment, so
`discovery.nmap_runner` is monkeypatched with a fake process so the
orchestrator's own logic runs deterministically.

Invariants exercised (contracts/http-api-delta.md §1):
- overrides are applied into the run's params_used / profile_snapshot;
- the saved DiscoveryProfile row is unchanged (FR-017, SC-004);
- a disallowed scan_params key is rejected (FR-018) — no such string ever
  reaches the nmap command line;
- any present override produces a fresh run (cache bypassed, R2).
"""
import time

from asset_dashboard.discovery import nmap_runner

VOIP_PROFILE = {
    "name": "VoIP Infrastructure Audit (overrides)",
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
</nmaprun>
"""


class _FakeProcess:
    def __init__(self, stdout="", stderr="", returncode=0):
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode

    def communicate(self):
        return self._stdout, self._stderr

    def poll(self):
        return self.returncode

    def terminate(self):
        pass


def _patch_successful_scan(monkeypatch, captured=None):
    def fake_start_nmap(
        target_scope, port_spec, scan_params, extracted_fields=None, selected_scripts=None
    ):
        if captured is not None:
            captured.append(
                {
                    "target_scope": target_scope,
                    "port_spec": port_spec,
                    "scan_params": scan_params,
                    "extracted_fields": extracted_fields,
                    "selected_scripts": selected_scripts,
                }
            )
        return nmap_runner.NmapRunHandle(
            process=_FakeProcess(stdout=SAMPLE_XML, returncode=0), command=["nmap"]
        )

    monkeypatch.setattr(nmap_runner, "start_nmap", fake_start_nmap)


def _poll_until_finished(authed_client, run_id, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        run = authed_client.get(f"/api/runs/{run_id}").json()
        if run["status"] != "running":
            return run
        time.sleep(0.02)
    raise TimeoutError(f"run {run_id} did not finish within {timeout}s")


def test_overrides_applied_to_run_snapshot_and_profile_unchanged(authed_client, monkeypatch):
    """port_spec / scan_params / extracted_fields overrides land on the run;
    the saved profile is unchanged (FR-017, SC-004)."""
    captured: list[dict] = []
    _patch_successful_scan(monkeypatch, captured=captured)
    profile = authed_client.post("/api/profiles", json=VOIP_PROFILE).json()

    resp = authed_client.post(
        f"/api/profiles/{profile['id']}/runs",
        json={
            "target_scope": ["10.10.0.9"],
            "port_spec": "22,80,443",
            "scan_params": {"timing": "T4"},
            "extracted_fields": ["open_ports"],
        },
    )
    assert resp.status_code == 202
    run = _poll_until_finished(authed_client, resp.json()["run_id"])

    params = run["params_used"]
    assert params["target_scope"] == ["10.10.0.9"]
    assert params["port_spec"] == "22,80,443"
    assert params["scan_params"]["timing"] == "T4"
    assert params["extracted_fields"] == ["open_ports"]
    # profile_snapshot carries the same effective params for the audit trail.
    assert run["profile_snapshot"]["port_spec"] == "22,80,443"
    assert run["profile_snapshot"]["scan_params"]["timing"] == "T4"

    # The effective params actually reached the (fake) nmap builder.
    assert captured and captured[-1]["port_spec"] == "22,80,443"
    assert captured[-1]["scan_params"]["timing"] == "T4"

    # SC-004: the saved profile is untouched.
    unchanged = authed_client.get(f"/api/profiles/{profile['id']}").json()
    assert unchanged["port_spec"] == VOIP_PROFILE["port_spec"]
    assert unchanged["scan_params"] == VOIP_PROFILE["scan_params"]
    assert unchanged["extracted_fields"] == VOIP_PROFILE["extracted_fields"]
    assert unchanged["target_scope"] == VOIP_PROFILE["target_scope"]


def test_disallowed_scan_params_key_is_rejected(authed_client):
    """A raw-flag-looking key is rejected with a validation error (FR-018)."""
    profile = authed_client.post("/api/profiles", json=VOIP_PROFILE).json()

    resp = authed_client.post(
        f"/api/profiles/{profile['id']}/runs",
        json={"scan_params": {"script": "x"}},
    )
    assert resp.status_code == 422
    assert "scan_params" in resp.json()["error"]["fields"]


def test_invalid_port_spec_override_is_rejected(authed_client):
    profile = authed_client.post("/api/profiles", json=VOIP_PROFILE).json()
    resp = authed_client.post(
        f"/api/profiles/{profile['id']}/runs",
        json={"port_spec": "not-a-port"},
    )
    assert resp.status_code == 422
    assert "port_spec" in resp.json()["error"]["fields"]


def test_unknown_extracted_field_override_is_rejected(authed_client):
    profile = authed_client.post("/api/profiles", json=VOIP_PROFILE).json()
    resp = authed_client.post(
        f"/api/profiles/{profile['id']}/runs",
        json={"extracted_fields": ["open_ports", "banner_grab"]},
    )
    assert resp.status_code == 422
    assert "extracted_fields" in resp.json()["error"]["fields"]


def test_param_override_bypasses_cache(authed_client, monkeypatch):
    """A completed run exists and is fresh, yet a param override forces a new,
    non-cached run (R2)."""
    _patch_successful_scan(monkeypatch)
    profile = authed_client.post("/api/profiles", json=VOIP_PROFILE).json()

    # First unchanged run — completes and becomes a cache candidate.
    first = authed_client.post(f"/api/profiles/{profile['id']}/runs", json={})
    assert first.status_code == 202
    _poll_until_finished(authed_client, first.json()["run_id"])

    # An unchanged relaunch is served from cache (200).
    cached = authed_client.post(f"/api/profiles/{profile['id']}/runs", json={})
    assert cached.status_code == 200
    assert cached.json()["served_from_cache"] is True

    # A param override forces a fresh run (202, not served from cache).
    overridden = authed_client.post(
        f"/api/profiles/{profile['id']}/runs", json={"scan_params": {"timing": "T5"}}
    )
    assert overridden.status_code == 202
    run = _poll_until_finished(authed_client, overridden.json()["run_id"])
    assert run["served_from_cache"] is False
    assert run["params_used"]["scan_params"]["timing"] == "T5"

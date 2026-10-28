"""Contract tests for /api/profiles/{id}/runs, /api/runs/* (FR-015-FR-021, FR-043).

`nmap` is not installed in this test environment, so `discovery.nmap_runner`
is monkeypatched with a fake process to exercise the orchestrator's own
logic (status transitions, concurrency, cancellation) deterministically,
without depending on an actual nmap binary.
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


def _patch_successful_scan(monkeypatch, xml=SAMPLE_XML):
    def fake_start_nmap(
        target_scope, port_spec, scan_params, extracted_fields=None, selected_scripts=None
    ):
        return nmap_runner.NmapRunHandle(
            process=_FakeProcess(stdout=xml, returncode=0), command=["nmap"]
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


def test_start_run_returns_202_and_completes_with_results(authed_client, monkeypatch):
    _patch_successful_scan(monkeypatch)
    profile = authed_client.post("/api/profiles", json=VOIP_PROFILE).json()

    resp = authed_client.post(f"/api/profiles/{profile['id']}/runs", json={})
    assert resp.status_code == 202
    run_id = resp.json()["run_id"]

    run = _poll_until_finished(authed_client, run_id)
    assert run["status"] == "completed"
    assert run["summary"]["hosts"] == 1

    results = authed_client.get(f"/api/runs/{run_id}/results").json()
    assert len(results) == 1
    assert results[0]["address"] == "10.10.0.5"
    assert results[0]["management_link"] is None  # FR-004: capability removed
    assert any(p["port"] == 5060 for p in results[0]["open_ports"])


def test_duplicate_concurrent_run_of_same_profile_returns_409(authed_client, monkeypatch):
    # A scan that "hangs" long enough for us to attempt a second, concurrent start.
    hang_event = __import__("threading").Event()

    class _HangingProcess(_FakeProcess):
        def communicate(self):
            hang_event.wait(timeout=2.0)
            return self._stdout, self._stderr

    def fake_start_nmap(
        target_scope, port_spec, scan_params, extracted_fields=None, selected_scripts=None
    ):
        return nmap_runner.NmapRunHandle(
            process=_HangingProcess(stdout=SAMPLE_XML, returncode=0), command=["nmap"]
        )

    monkeypatch.setattr(nmap_runner, "start_nmap", fake_start_nmap)

    profile = authed_client.post("/api/profiles", json=VOIP_PROFILE).json()
    first = authed_client.post(f"/api/profiles/{profile['id']}/runs", json={})
    assert first.status_code == 202

    second = authed_client.post(f"/api/profiles/{profile['id']}/runs", json={})
    assert second.status_code == 409

    # Let the first run finish and WAIT for it, so its background thread
    # never outlives the test (it would otherwise try to write to this
    # test's DB after teardown, in the gap before the next test's fixture
    # rebinds the engine — a real race, not just test hygiene).
    hang_event.set()
    _poll_until_finished(authed_client, first.json()["run_id"])


def test_empty_target_result_is_completed_with_zero_hosts_not_failed(authed_client, monkeypatch):
    _patch_successful_scan(monkeypatch, xml="<?xml version='1.0'?><nmaprun></nmaprun>")
    profile = authed_client.post("/api/profiles", json=VOIP_PROFILE).json()

    resp = authed_client.post(f"/api/profiles/{profile['id']}/runs", json={})
    run_id = resp.json()["run_id"]
    run = _poll_until_finished(authed_client, run_id)

    assert run["status"] == "completed"
    assert run["summary"]["hosts"] == 0


def test_missing_nmap_binary_marks_run_failed_with_error_detail(authed_client, monkeypatch):
    def fake_start_nmap(*args, **kwargs):
        raise nmap_runner.NmapNotAvailableError("nmap is not installed or not on PATH.")

    monkeypatch.setattr(nmap_runner, "start_nmap", fake_start_nmap)

    profile = authed_client.post("/api/profiles", json=VOIP_PROFILE).json()
    resp = authed_client.post(f"/api/profiles/{profile['id']}/runs", json={})
    run_id = resp.json()["run_id"]
    run = _poll_until_finished(authed_client, run_id)

    assert run["status"] == "failed"
    assert "nmap" in run["error_detail"]


def test_cancel_running_run_retains_partial_results(authed_client, monkeypatch):
    import threading

    release_event = threading.Event()

    class _CancellableProcess(_FakeProcess):
        def terminate(self):
            self.returncode = -15
            release_event.set()

        def communicate(self):
            release_event.wait(timeout=2.0)
            return self._stdout, self._stderr

    def fake_start_nmap(
        target_scope, port_spec, scan_params, extracted_fields=None, selected_scripts=None
    ):
        return nmap_runner.NmapRunHandle(
            process=_CancellableProcess(stdout=SAMPLE_XML, returncode=0), command=["nmap"]
        )

    monkeypatch.setattr(nmap_runner, "start_nmap", fake_start_nmap)

    profile = authed_client.post("/api/profiles", json=VOIP_PROFILE).json()
    resp = authed_client.post(f"/api/profiles/{profile['id']}/runs", json={})
    run_id = resp.json()["run_id"]

    cancel_resp = authed_client.post(f"/api/runs/{run_id}/cancel")
    assert cancel_resp.status_code == 200

    run = _poll_until_finished(authed_client, run_id)
    assert run["status"] == "cancelled"
    # Partial results retained from the XML captured up to cancellation (FR-017).
    results = authed_client.get(f"/api/runs/{run_id}/results").json()
    assert len(results) == 1


def test_run_routes_require_authentication(client):
    resp = client.get("/api/runs/does-not-exist")
    assert resp.status_code == 401


def test_start_run_with_target_override_uses_override_not_profile_target(
    authed_client, monkeypatch
):
    """FR-003b/c: an override is used for this run only, not persisted."""
    _patch_successful_scan(monkeypatch)
    profile = authed_client.post("/api/profiles", json=VOIP_PROFILE).json()

    resp = authed_client.post(
        f"/api/profiles/{profile['id']}/runs", json={"target_scope": ["10.10.0.9"]}
    )
    assert resp.status_code == 202
    run_id = resp.json()["run_id"]
    run = _poll_until_finished(authed_client, run_id)
    assert run["params_used"]["target_scope"] == ["10.10.0.9"]

    unchanged = authed_client.get(f"/api/profiles/{profile['id']}").json()
    assert unchanged["target_scope"] == VOIP_PROFILE["target_scope"]


def test_start_run_on_target_less_profile_without_override_returns_400_target_required(
    authed_client,
):
    target_less = dict(VOIP_PROFILE, name="Target-less profile", target_scope=[])
    profile = authed_client.post("/api/profiles", json=target_less).json()

    resp = authed_client.post(f"/api/profiles/{profile['id']}/runs", json={})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "target_required"


def test_start_run_with_invalid_target_override_returns_422(authed_client):
    profile = authed_client.post("/api/profiles", json=VOIP_PROFILE).json()

    resp = authed_client.post(
        f"/api/profiles/{profile['id']}/runs", json={"target_scope": ["not-a-target!!"]}
    )
    assert resp.status_code == 422
    assert "target_scope" in resp.json()["error"]["fields"]


def test_start_run_on_target_less_profile_with_override_succeeds(authed_client, monkeypatch):
    _patch_successful_scan(monkeypatch)
    target_less = dict(VOIP_PROFILE, name="Target-less profile 2", target_scope=[])
    profile = authed_client.post("/api/profiles", json=target_less).json()

    resp = authed_client.post(
        f"/api/profiles/{profile['id']}/runs", json={"target_scope": ["10.10.0.9"]}
    )
    assert resp.status_code == 202
    run = _poll_until_finished(authed_client, resp.json()["run_id"])
    assert run["status"] == "completed"

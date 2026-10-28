"""Integration tests for the standalone default-credential tool.

Feature 008 (US5): a started check appears as `running` immediately and polls
to `completed`; a worker failure ends `failed` with an `error_detail` (never
stuck). Also retained from earlier: a scheduled task fires via tick() and
produces an equivalent run, and a discovery-profile run never triggers the
check (FR-020 decoupling)."""

import threading
import time

from asset_dashboard.compliance import credential_check
from asset_dashboard.compliance.probes.base import ProbeAttemptResult
from asset_dashboard.db.base import session_scope
from asset_dashboard.db.models import AuditEventType, AuditLogEntry, DefaultCredentialEntry
from asset_dashboard.discovery import nmap_runner
from asset_dashboard.scheduling.engine import tick

PROFILE = {
    "name": "Decoupled profile",
    "description": "",
    "target_scope": ["10.0.0.1"],
    "port_spec": "22",
    "scan_params": {"timing": "T3"},
    "extracted_fields": ["open_ports"],
    "compliance_settings": {"default_credentials": True},  # legacy key, must be ignored
    "cache_freshness_seconds": 3600,
}

SAMPLE_XML = """<?xml version="1.0"?>
<nmaprun>
  <host><status state="up"/><address addr="10.0.0.1" addrtype="ipv4"/>
    <ports><port protocol="tcp" portid="22"><state state="open"/>
      <service name="ssh"/>
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


def _poll_tool_run(client, run_id, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        run = client.get(f"/api/tools/credential-check/runs/{run_id}").json()
        if run["status"] != "running":
            return run
        time.sleep(0.02)
    raise TimeoutError("tool run did not finish")


def _seed_ssh_dict(n=10):
    with session_scope() as session:
        entry = DefaultCredentialEntry(
            vendor="Test",
            service="ssh",
            credentials=[{"username": f"u{i}", "secret": f"s{i}"} for i in range(n)],
            success_keywords=["ok"],
        )
        session.add(entry)
        session.flush()
        return entry.id


def test_run_appears_running_then_completes(authed_client, monkeypatch):
    """FR-112: the run is observable as `running` before it finishes, then
    transitions to `completed` via polling."""
    monkeypatch.setattr(credential_check.time, "sleep", lambda s: None)
    gate = threading.Event()

    def blocking_probe(*a, **k):
        gate.wait(timeout=2.0)
        return ProbeAttemptResult(matched=False, response_excerpt="")

    monkeypatch.setitem(credential_check._PROBES, "ssh", blocking_probe)
    dict_id = _seed_ssh_dict(n=1)

    resp = authed_client.post(
        "/api/tools/credential-check",
        json={"target_scope": ["10.0.0.1"], "port": 22, "service": "ssh", "dictionary_id": dict_id},
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "running"
    run_id = resp.json()["run_id"]

    # Visible as running before the (gated) worker completes.
    assert (
        authed_client.get(f"/api/tools/credential-check/runs/{run_id}").json()["status"]
        == "running"
    )

    gate.set()
    done = _poll_tool_run(authed_client, run_id)
    assert done["status"] == "completed"


def test_on_demand_run_is_audited(authed_client, monkeypatch):
    monkeypatch.setattr(credential_check.time, "sleep", lambda s: None)
    monkeypatch.setitem(
        credential_check._PROBES,
        "ssh",
        lambda *a, **k: ProbeAttemptResult(matched=False, response_excerpt=""),
    )
    dict_id = _seed_ssh_dict(n=10)

    resp = authed_client.post(
        "/api/tools/credential-check",
        json={"target_scope": ["10.0.0.1"], "port": 22, "service": "ssh", "dictionary_id": dict_id},
    )
    assert resp.status_code == 201
    run_id = resp.json()["run_id"]
    detail = _poll_tool_run(authed_client, run_id)
    # Exhaustive audit under the default ceiling (= dictionary size).
    assert detail["results"][0]["attempts_made"] == 10

    with session_scope() as session:
        count = session.query(AuditLogEntry).filter_by(event_type=AuditEventType.TOOL_CHECK).count()
        assert count >= 1


def test_worker_failure_marks_run_failed_with_error_detail(authed_client, monkeypatch):
    """FR-117: a worker exception ends the run `failed` with an error_detail,
    never stuck `running`."""
    from asset_dashboard.tools.credential_tool import service as tool_service

    def boom(*a, **k):
        raise RuntimeError("probe exploded")

    monkeypatch.setattr(tool_service, "check_default_credentials", boom)
    dict_id = _seed_ssh_dict(n=1)

    resp = authed_client.post(
        "/api/tools/credential-check",
        json={"target_scope": ["10.0.0.1"], "port": 22, "service": "ssh", "dictionary_id": dict_id},
    )
    run_id = resp.json()["run_id"]
    done = _poll_tool_run(authed_client, run_id)
    assert done["status"] == "failed"
    assert done["error_detail"]


def test_scheduled_task_fires_via_tick_and_produces_equivalent_run(authed_client, monkeypatch):
    monkeypatch.setattr(credential_check.time, "sleep", lambda s: None)
    monkeypatch.setitem(
        credential_check._PROBES,
        "ssh",
        lambda *a, **k: ProbeAttemptResult(matched=False, response_excerpt=""),
    )

    created = authed_client.post(
        "/api/tools/credential-check/tasks",
        json={
            "target_scope": ["10.0.0.1"],
            "port": 22,
            "service": "ssh",
            "recurrence": {"type": "interval", "seconds": 1},
        },
    ).json()

    from datetime import timedelta

    from asset_dashboard.db.models import ToolTask, utcnow

    with session_scope() as session:
        task = session.get(ToolTask, created["id"])
        task.next_run_at = utcnow() - timedelta(seconds=1)

    with session_scope() as session:
        started = tick(session)
        assert len(started) == 1

    runs = authed_client.get("/api/tools/credential-check/runs").json()
    assert any(r["id"] == started[0] for r in runs)


def test_discovery_profile_run_does_not_trigger_default_credential_check(
    authed_client, monkeypatch
):
    def fake_start_nmap(
        target_scope, port_spec, scan_params, extracted_fields=None, selected_scripts=None
    ):
        return nmap_runner.NmapRunHandle(process=_FakeProcess(SAMPLE_XML), command=["nmap"])

    monkeypatch.setattr(nmap_runner, "start_nmap", fake_start_nmap)

    before = authed_client.get("/api/tools/credential-check/runs").json()

    profile = authed_client.post("/api/profiles", json=PROFILE).json()
    start = authed_client.post(f"/api/profiles/{profile['id']}/runs", json={})
    _poll_until_finished(authed_client, start.json()["run_id"])

    after = authed_client.get("/api/tools/credential-check/runs").json()
    assert len(after) == len(before)  # no ToolCheckRun was created by the profile run

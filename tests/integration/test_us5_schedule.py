"""Integration test for User Story 5: scheduled discovery jobs.
Calls scheduling.engine.tick() directly for determinism, rather than
waiting on the real background heartbeat (see spec.md US5 Independent Test:
attach a schedule, confirm next-run is shown, let it trigger, confirm a
run is produced and recorded in history; overlap -> no duplicate; missed
schedule -> catch-up policy)."""
import time
from datetime import timedelta

from asset_dashboard.db.base import session_scope
from asset_dashboard.db.models import Schedule, utcnow
from asset_dashboard.discovery import nmap_runner
from asset_dashboard.scheduling.engine import tick

PROFILE = {
    "name": "Nightly Inventory",
    "description": "",
    "target_scope": ["10.10.0.0/24"],
    "port_spec": "22",
    "scan_params": {},
    "extracted_fields": ["open_ports", "service_version"],
    "compliance_settings": {},
    "cache_freshness_seconds": 3600,
    "host_links": [],
}

SAMPLE_XML = """<?xml version="1.0"?>
<nmaprun>
  <host><status state="up"/><address addr="10.10.0.5" addrtype="ipv4"/><ports/></host>
</nmaprun>
"""


class _FakeProcess:
    def __init__(self, stdout, hang_event=None):
        self.stdout = stdout
        self.returncode = 0
        self._hang_event = hang_event

    def communicate(self):
        if self._hang_event is not None:
            self._hang_event.wait(timeout=2.0)
        return self.stdout, ""

    def poll(self):
        return self.returncode

    def terminate(self):
        pass


def _patch(monkeypatch, hang_event=None):
    def fake_start_nmap(
        target_scope, port_spec, scan_params, extracted_fields=None, selected_scripts=None
    ):
        return nmap_runner.NmapRunHandle(
            process=_FakeProcess(SAMPLE_XML, hang_event=hang_event), command=["nmap"]
        )

    monkeypatch.setattr(nmap_runner, "start_nmap", fake_start_nmap)


def _poll_until_finished(client, run_id, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        run = client.get(f"/api/runs/{run_id}").json()
        if run["status"] != "running":
            return run
        time.sleep(0.02)
    raise TimeoutError("run did not finish")


def test_due_schedule_triggers_a_recorded_run(authed_client, monkeypatch):
    _patch(monkeypatch)
    profile = authed_client.post("/api/profiles", json=PROFILE).json()
    authed_client.post(
        f"/api/profiles/{profile['id']}/schedules",
        json={"recurrence": {"type": "interval", "seconds": 60}},
    )

    # Force the schedule due "now" and tick.
    with session_scope() as session:
        schedule = session.query(Schedule).filter_by(profile_id=profile["id"]).one()
        schedule.next_run_at = utcnow()
        session.add(schedule)

    with session_scope() as session:
        started = tick(session)
    assert len(started) == 1

    run = _poll_until_finished(authed_client, started[0])
    assert run["status"] == "completed"
    assert run["trigger"] == "scheduled"

    history = authed_client.get("/api/history").json()
    assert any(h["id"] == started[0] for h in history)

    # next_run_at advanced past "now".
    with session_scope() as session:
        schedule = session.query(Schedule).filter_by(profile_id=profile["id"]).one()
        assert schedule.next_run_at > utcnow()


def test_overlap_skip_policy_prevents_duplicate_concurrent_run(authed_client, monkeypatch):
    import threading

    hang_event = threading.Event()
    _patch(monkeypatch, hang_event=hang_event)

    profile = authed_client.post("/api/profiles", json=PROFILE).json()
    authed_client.post(
        f"/api/profiles/{profile['id']}/schedules",
        json={"recurrence": {"type": "interval", "seconds": 60}, "overlap_policy": "skip"},
    )

    # Start a manual run that will "hang" (simulating an in-progress scan).
    manual = authed_client.post(f"/api/profiles/{profile['id']}/runs", json={})
    assert manual.status_code == 202

    with session_scope() as session:
        schedule = session.query(Schedule).filter_by(profile_id=profile["id"]).one()
        schedule.next_run_at = utcnow()
        session.add(schedule)

    with session_scope() as session:
        started = tick(session)

    # The scheduled trigger must NOT launch a duplicate concurrent run.
    assert started == []

    hang_event.set()  # release the hanging manual run so its thread finishes
    _poll_until_finished(authed_client, manual.json()["run_id"])


def test_catch_up_skip_policy_jumps_forward_without_running(authed_client, monkeypatch):
    _patch(monkeypatch)
    profile = authed_client.post("/api/profiles", json=PROFILE).json()
    authed_client.post(
        f"/api/profiles/{profile['id']}/schedules",
        json={
            "recurrence": {"type": "interval", "seconds": 60},
            "catch_up_policy": "skip",
        },
    )

    # Simulate having been down for a long time: next_run_at is far in the past.
    with session_scope() as session:
        schedule = session.query(Schedule).filter_by(profile_id=profile["id"]).one()
        schedule.next_run_at = utcnow() - timedelta(hours=5)
        session.add(schedule)

    with session_scope() as session:
        started = tick(session)

    assert started == []  # skipped, not run
    with session_scope() as session:
        schedule = session.query(Schedule).filter_by(profile_id=profile["id"]).one()
        assert schedule.next_run_at > utcnow()  # jumped forward to a future occurrence


def test_catch_up_run_once_policy_runs_the_missed_occurrence(authed_client, monkeypatch):
    _patch(monkeypatch)
    profile = authed_client.post("/api/profiles", json=PROFILE).json()
    authed_client.post(
        f"/api/profiles/{profile['id']}/schedules",
        json={
            "recurrence": {"type": "interval", "seconds": 60},
            "catch_up_policy": "run_once",
        },
    )

    with session_scope() as session:
        schedule = session.query(Schedule).filter_by(profile_id=profile["id"]).one()
        schedule.next_run_at = utcnow() - timedelta(hours=5)
        session.add(schedule)

    with session_scope() as session:
        started = tick(session)

    assert len(started) == 1  # the missed run_once occurrence fires
    # tick() -> start_run() spawns a real background thread for the run;
    # wait for it so it never outlives this test (same hazard as a
    # manually-started run — see test_due_schedule_triggers_a_recorded_run).
    _poll_until_finished(authed_client, started[0])

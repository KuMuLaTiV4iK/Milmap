"""Integration test for feature-005 User Story 2: unit-based interval schedule.

An interval `{every, unit}` schedule seeds next_run_at ≈ now + interval,
fires, and reschedules (keeps recurring); invalid every/unit are rejected.
Drives the engine via tick() directly for determinism."""
import time
from datetime import timedelta

from asset_dashboard.db.base import session_scope
from asset_dashboard.db.models import Schedule, utcnow
from asset_dashboard.discovery import nmap_runner
from asset_dashboard.scheduling.engine import tick

PROFILE = {
    "name": "Every two hours",
    "description": "",
    "target_scope": ["10.10.0.0/24"],
    "port_spec": "22",
    "scan_params": {},
    "extracted_fields": ["open_ports"],
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
    def __init__(self, stdout):
        self.stdout = stdout
        self.returncode = 0

    def communicate(self):
        return self.stdout, ""

    def poll(self):
        return self.returncode

    def terminate(self):
        pass


def _patch(monkeypatch):
    def fake_start_nmap(
        target_scope, port_spec, scan_params, extracted_fields=None, selected_scripts=None
    ):
        return nmap_runner.NmapRunHandle(process=_FakeProcess(SAMPLE_XML), command=["nmap"])

    monkeypatch.setattr(nmap_runner, "start_nmap", fake_start_nmap)


def _poll_until_finished(client, run_id, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        run = client.get(f"/api/runs/{run_id}").json()
        if run["status"] != "running":
            return run
        time.sleep(0.02)
    raise TimeoutError("run did not finish")


def test_interval_unit_schedule_seeds_fires_and_reschedules(authed_client, monkeypatch):
    _patch(monkeypatch)
    profile = authed_client.post("/api/profiles", json=PROFILE).json()

    before = utcnow()
    resp = authed_client.post(
        f"/api/profiles/{profile['id']}/schedules",
        json={"recurrence": {"type": "interval", "every": 2, "unit": "hour"}},
    )
    assert resp.status_code == 201

    with session_scope() as session:
        schedule = session.query(Schedule).filter_by(profile_id=profile["id"]).one()
        # next_run_at ≈ now + 2h.
        assert schedule.next_run_at >= before + timedelta(hours=2) - timedelta(seconds=5)
        assert schedule.next_run_at <= before + timedelta(hours=2) + timedelta(seconds=5)
        # Force it due.
        schedule.next_run_at = utcnow()
        session.add(schedule)

    with session_scope() as session:
        started = tick(session)
    assert len(started) == 1
    _poll_until_finished(authed_client, started[0])

    # It keeps recurring: still enabled, next_run advanced ~2h past the fire.
    with session_scope() as session:
        schedule = session.query(Schedule).filter_by(profile_id=profile["id"]).one()
        assert schedule.enabled is True
        assert schedule.next_run_at > utcnow() + timedelta(hours=1)


def test_invalid_interval_every_rejected(authed_client):
    profile = authed_client.post("/api/profiles", json=PROFILE).json()
    resp = authed_client.post(
        f"/api/profiles/{profile['id']}/schedules",
        json={"recurrence": {"type": "interval", "every": 0, "unit": "hour"}},
    )
    assert resp.status_code == 422
    assert "recurrence" in resp.json()["error"]["fields"]


def test_invalid_interval_unit_rejected(authed_client):
    profile = authed_client.post("/api/profiles", json=PROFILE).json()
    resp = authed_client.post(
        f"/api/profiles/{profile['id']}/schedules",
        json={"recurrence": {"type": "interval", "every": 2, "unit": "fortnight"}},
    )
    assert resp.status_code == 422
    assert "recurrence" in resp.json()["error"]["fields"]

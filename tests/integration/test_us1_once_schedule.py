"""Integration test for feature-005 User Story 1: one-time ("once") schedule.

A once schedule fires exactly once, then is marked completed (enabled=False)
and never runs again; a past run_at is rejected at create time. Drives the
engine via tick() directly for determinism (same pattern as
tests/integration/test_us5_schedule.py)."""

import time
from datetime import timedelta

from asset_dashboard.db.base import session_scope
from asset_dashboard.db.models import Schedule, utcnow
from asset_dashboard.discovery import nmap_runner
from asset_dashboard.scheduling.engine import tick

PROFILE = {
    "name": "One-off audit",
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


def test_once_fires_exactly_once_then_completes(authed_client, monkeypatch):
    _patch(monkeypatch)
    profile = authed_client.post("/api/profiles", json=PROFILE).json()

    run_at = (utcnow() + timedelta(minutes=1)).isoformat()
    resp = authed_client.post(
        f"/api/profiles/{profile['id']}/schedules",
        json={"recurrence": {"type": "once", "run_at": run_at}, "target_scope": ["127.0.0.1"]},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["enabled"] is True

    # Force due and tick once -> exactly one run, schedule becomes completed.
    with session_scope() as session:
        schedule = session.query(Schedule).filter_by(profile_id=profile["id"]).one()
        schedule.next_run_at = utcnow()
        session.add(schedule)

    with session_scope() as session:
        started = tick(session)
    assert len(started) == 1
    _poll_until_finished(authed_client, started[0])

    with session_scope() as session:
        schedule = session.query(Schedule).filter_by(profile_id=profile["id"]).one()
        assert schedule.enabled is False
        assert schedule.last_triggered_at is not None

    # A second tick does nothing — it never re-fires.
    with session_scope() as session:
        started_again = tick(session)
    assert started_again == []


def test_once_past_run_at_is_rejected(authed_client):
    profile = authed_client.post("/api/profiles", json=PROFILE).json()
    run_at = (utcnow() - timedelta(minutes=1)).isoformat()
    resp = authed_client.post(
        f"/api/profiles/{profile['id']}/schedules",
        json={"recurrence": {"type": "once", "run_at": run_at}},
    )
    assert resp.status_code == 422
    assert "recurrence" in resp.json()["error"]["fields"]

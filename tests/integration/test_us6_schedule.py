"""Integration test for User Story 6: schedule discovery-profile scans
with their own target, multiple schedules per profile, firing via
tick(), and creating a schedule from a past scan in history
(FR-020-FR-023)."""

import time

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
}

TARGET_LESS_PROFILE = dict(PROFILE, name="Target-less nightly", target_scope=[])

SAMPLE_XML = """<?xml version="1.0"?>
<nmaprun>
  <host><status state="up"/><address addr="10.10.0.5" addrtype="ipv4"/><ports/></host>
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


def _patch(monkeypatch):
    def fake_start_nmap(
        target_scope, port_spec, scan_params, extracted_fields=None, selected_scripts=None
    ):
        return nmap_runner.NmapRunHandle(process=_FakeProcess(), command=["nmap"])

    monkeypatch.setattr(nmap_runner, "start_nmap", fake_start_nmap)


def _poll_until_finished(client, run_id, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        run = client.get(f"/api/runs/{run_id}").json()
        if run["status"] != "running":
            return run
        time.sleep(0.02)
    raise TimeoutError("run did not finish")


def test_create_schedule_with_own_target_and_fire_via_tick(authed_client, monkeypatch):
    _patch(monkeypatch)
    profile = authed_client.post("/api/profiles", json=TARGET_LESS_PROFILE).json()
    created = authed_client.post(
        f"/api/profiles/{profile['id']}/schedules",
        json={
            "recurrence": {"type": "interval", "seconds": 3600},
            "target_scope": ["10.0.0.5"],
        },
    ).json()

    with session_scope() as session:
        schedule = session.get(Schedule, created["id"])
        schedule.next_run_at = utcnow()
        session.add(schedule)

    with session_scope() as session:
        started = tick(session)
    assert len(started) == 1

    run = _poll_until_finished(authed_client, started[0])
    assert run["status"] == "completed"
    assert run["trigger"] == "scheduled"
    assert run["params_used"]["target_scope"] == ["10.0.0.5"]

    reloaded = authed_client.get(f"/api/profiles/{profile['id']}").json()
    assert reloaded["target_scope"] == []


def test_multiple_schedules_per_profile_each_fire_independently(authed_client, monkeypatch):
    _patch(monkeypatch)
    profile = authed_client.post("/api/profiles", json=PROFILE).json()
    first = authed_client.post(
        f"/api/profiles/{profile['id']}/schedules",
        json={"recurrence": {"type": "interval", "seconds": 3600}, "label": "a"},
    ).json()
    second = authed_client.post(
        f"/api/profiles/{profile['id']}/schedules",
        json={"recurrence": {"type": "interval", "seconds": 7200}, "label": "b"},
    ).json()

    with session_scope() as session:
        for sid in (first["id"], second["id"]):
            s = session.get(Schedule, sid)
            s.next_run_at = utcnow()
            session.add(s)

    with session_scope() as session:
        started = tick(session)
    assert len(started) == 2


def test_create_schedule_from_history_reuses_profile_and_target(authed_client, monkeypatch):
    _patch(monkeypatch)
    profile = authed_client.post("/api/profiles", json=PROFILE).json()
    run_resp = authed_client.post(f"/api/profiles/{profile['id']}/runs", json={})
    run = _poll_until_finished(authed_client, run_resp.json()["run_id"])
    assert run["status"] == "completed"

    resp = authed_client.post(
        f"/api/runs/{run['id']}/schedule",
        json={"recurrence": {"type": "daily", "hour": 2, "minute": 0}},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["profile_id"] == profile["id"]
    assert body["target_scope"] == PROFILE["target_scope"]

    listed = authed_client.get(f"/api/profiles/{profile['id']}/schedules").json()
    assert any(s["id"] == body["id"] for s in listed)


def test_empty_target_schedule_rejected(authed_client):
    profile = authed_client.post("/api/profiles", json=TARGET_LESS_PROFILE).json()
    resp = authed_client.post(
        f"/api/profiles/{profile['id']}/schedules",
        json={"recurrence": {"type": "interval", "seconds": 3600}, "target_scope": []},
    )
    assert resp.status_code == 422


def test_invalid_target_schedule_rejected(authed_client):
    profile = authed_client.post("/api/profiles", json=PROFILE).json()
    resp = authed_client.post(
        f"/api/profiles/{profile['id']}/schedules",
        json={"recurrence": {"type": "interval", "seconds": 3600}, "target_scope": ["garbage!!"]},
    )
    assert resp.status_code == 422

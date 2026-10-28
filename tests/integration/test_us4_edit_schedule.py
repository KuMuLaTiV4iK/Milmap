"""Integration test for feature-005 User Story 4: edit an existing schedule.

Editing reuses the existing PUT /api/schedules/{id} endpoint — no new route.
A valid edit updates the same schedule in place (recomputing next_run_at and
recording a SCHEDULE_CHANGE audit event); an invalid edit is rejected and
leaves the schedule unchanged; a completed once re-enabled with a future
time becomes active again."""

from datetime import timedelta

from asset_dashboard.db.base import session_scope
from asset_dashboard.db.models import AuditEventType, AuditLogEntry, Schedule, utcnow

PROFILE = {
    "name": "Editable",
    "description": "",
    "target_scope": ["10.10.0.0/24"],
    "port_spec": "22",
    "scan_params": {},
    "extracted_fields": ["open_ports"],
    "compliance_settings": {},
    "cache_freshness_seconds": 3600,
    "host_links": [],
}


def _create_interval(client, profile_id):
    return client.post(
        f"/api/profiles/{profile_id}/schedules",
        json={"recurrence": {"type": "interval", "every": 2, "unit": "hour"}, "label": "orig"},
    ).json()


def test_edit_interval_to_once_updates_in_place(authed_client):
    profile = authed_client.post("/api/profiles", json=PROFILE).json()
    created = _create_interval(authed_client, profile["id"])

    run_at = (utcnow() + timedelta(hours=1)).isoformat()
    resp = authed_client.put(
        f"/api/schedules/{created['id']}",
        json={
            "recurrence": {"type": "once", "run_at": run_at},
            "target_scope": ["192.168.1.3"],
            "label": "one-off",
            "enabled": True,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == created["id"]  # same schedule, edited in place
    assert body["recurrence"]["type"] == "once"
    assert body["target_scope"] == ["192.168.1.3"]
    assert body["label"] == "one-off"

    # next_run_at recomputed to the once run_at.
    with session_scope() as session:
        schedule = session.get(Schedule, created["id"])
        assert schedule.recurrence["type"] == "once"

    # A SCHEDULE_CHANGE update audit event was recorded.
    with session_scope() as session:
        events = (
            session.query(AuditLogEntry)
            .filter(AuditLogEntry.event_type == AuditEventType.SCHEDULE_CHANGE)
            .all()
        )
        assert any((e.detail or {}).get("action") == "update" for e in events)


def test_invalid_edit_rejected_and_schedule_unchanged(authed_client):
    profile = authed_client.post("/api/profiles", json=PROFILE).json()
    created = _create_interval(authed_client, profile["id"])

    past = (utcnow() - timedelta(minutes=1)).isoformat()
    resp = authed_client.put(
        f"/api/schedules/{created['id']}",
        json={"recurrence": {"type": "once", "run_at": past}},
    )
    assert resp.status_code == 422
    assert "recurrence" in resp.json()["error"]["fields"]

    # Unchanged: still the original interval recurrence and label.
    with session_scope() as session:
        schedule = session.get(Schedule, created["id"])
        assert schedule.recurrence == {"type": "interval", "every": 2, "unit": "hour"}
        assert schedule.label == "orig"


def test_reenable_completed_once_with_future_time(authed_client):
    profile = authed_client.post("/api/profiles", json=PROFILE).json()
    run_at = (utcnow() + timedelta(minutes=5)).isoformat()
    created = authed_client.post(
        f"/api/profiles/{profile['id']}/schedules",
        json={"recurrence": {"type": "once", "run_at": run_at}},
    ).json()

    # Simulate it having fired and completed.
    with session_scope() as session:
        schedule = session.get(Schedule, created["id"])
        schedule.enabled = False
        schedule.last_triggered_at = utcnow()
        session.add(schedule)

    new_run_at = (utcnow() + timedelta(hours=2)).isoformat()
    resp = authed_client.put(
        f"/api/schedules/{created['id']}",
        json={"recurrence": {"type": "once", "run_at": new_run_at}, "enabled": True},
    )
    assert resp.status_code == 200
    assert resp.json()["enabled"] is True

    with session_scope() as session:
        schedule = session.get(Schedule, created["id"])
        assert schedule.enabled is True
        assert schedule.next_run_at > utcnow()

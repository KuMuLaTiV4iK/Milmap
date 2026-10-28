"""Integration test for feature-005 User Story 3: the localized schedules form.

GET /schedules renders a kind dropdown with Одноразово above Інтервал, a unit
dropdown of the five Ukrainian units, and a humanized (not raw-dict) recurrence
in the list."""

from datetime import timedelta

from asset_dashboard.db.base import session_scope
from asset_dashboard.db.models import Schedule, utcnow

PROFILE = {
    "name": "Form profile",
    "description": "",
    "target_scope": ["10.10.0.0/24"],
    "port_spec": "22",
    "scan_params": {},
    "extracted_fields": ["open_ports"],
    "compliance_settings": {},
    "cache_freshness_seconds": 3600,
    "host_links": [],
}


def test_schedule_form_renders_localized_and_ordered(authed_client):
    profile = authed_client.post("/api/profiles", json=PROFILE).json()
    authed_client.post(
        f"/api/profiles/{profile['id']}/schedules",
        json={"recurrence": {"type": "interval", "every": 2, "unit": "hour"}},
    )

    resp = authed_client.get("/schedules")
    assert resp.status_code == 200
    html = resp.text

    # Kind dropdown: Одноразово appears before Інтервал.
    assert "Одноразово" in html and "Інтервал" in html
    assert html.index("Одноразово") < html.index("Інтервал")

    # Unit dropdown contains all five Ukrainian units.
    for unit in ("хвилина", "година", "день", "тиждень", "місяць"):
        assert unit in html

    # List shows a humanized recurrence, not a raw Python dict.
    assert "Кожні 2 година" in html
    assert "{'type': 'interval'" not in html


def test_schedule_list_marks_completed_once(authed_client):
    profile = authed_client.post("/api/profiles", json=PROFILE).json()
    run_at = (utcnow() + timedelta(minutes=5)).isoformat()
    created = authed_client.post(
        f"/api/profiles/{profile['id']}/schedules",
        json={"recurrence": {"type": "once", "run_at": run_at}},
    ).json()

    # Simulate a fired one-time schedule (enabled=False + last_triggered_at).
    with session_scope() as session:
        schedule = session.get(Schedule, created["id"])
        schedule.enabled = False
        schedule.last_triggered_at = utcnow()
        session.add(schedule)

    html = authed_client.get("/schedules").text
    # The once label no longer duplicates the timestamp (shown in the dedicated
    # "Next run" column); it reads just "Одноразово" plus the completed badge.
    assert "Одноразово" in html
    assert "Виконано" in html

"""Feature 006 — Home page layout refinements (US1 + US2).

US1 (FR-001, FR-002, FR-005): the "Головна" heading and subtitle are gone,
the page is a two-column shell (profiles left, recent scans right), and the
recent-scans table drops the compliant/unknown/inconclusive columns while
keeping "Не відповідає".

US2 (FR-003, FR-006): up to 5 soonest-upcoming *enabled* schedules surface
in the left column, each linking to /schedules; disabled schedules are
excluded and an empty set renders the empty state, not an error.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from asset_dashboard.web.i18n import t


def test_home_drops_subtitle_and_compliance_columns(authed_client):
    page = authed_client.get("/", headers={"accept": "text/html"})
    assert page.status_code == 200
    text = page.text

    # FR-001: no subtitle paragraph.
    assert t("dashboard.subtitle") not in text

    # FR-005: the three compliance columns are gone, "Не відповідає" stays.
    # The removed-column headers are asserted as literals because their
    # catalog keys were deleted (T008); "Відповідає" (capital В) is the
    # compliant header, distinct from "Не відповідає".
    assert t("dashboard.col_non_compliant") in text  # "Не відповідає"
    assert "Відповідає" not in text
    assert "Невідомо" not in text
    assert "Непереконливо" not in text


def test_home_is_two_column_profiles_left_scans_right(authed_client):
    page = authed_client.get("/", headers={"accept": "text/html"})
    text = page.text
    assert "home-columns" in text
    left = text.index("home-col-left")
    right = text.index("home-col-right")
    # Left column (profiles) is rendered before the right column (scans).
    assert left < right
    # Profiles card lives in the left column, recent-scans in the right.
    assert text.index(t("dashboard.recent_profiles_title")) < right
    assert text.index(t("dashboard.recent_scans_title")) > left


def _make_enabled_schedule(session, *, profile_name, label, next_run_at, enabled=True):
    from asset_dashboard.db.models import DiscoveryProfile, Schedule

    profile = DiscoveryProfile(name=profile_name, target_scope=["10.0.0.0/24"], port_spec="22")
    session.add(profile)
    session.flush()
    schedule = Schedule(
        profile_id=profile.id,
        recurrence={"kind": "interval", "every": 1, "unit": "day"},
        target_scope=["10.0.0.0/24"],
        label=label,
        enabled=enabled,
        next_run_at=next_run_at,
    )
    session.add(schedule)
    session.flush()
    return schedule.id


def test_home_upcoming_schedules_enabled_only_sorted_limited(authed_client):
    from asset_dashboard.db.base import session_scope

    now = datetime.now()  # naive, matches Schedule.next_run_at column
    with session_scope() as session:
        # 6 enabled schedules (expect only the 5 soonest) + 1 disabled (excluded).
        for i in range(6):
            _make_enabled_schedule(
                session,
                profile_name=f"Sched profile {i}",
                label=f"Upcoming {i}",
                next_run_at=now + timedelta(hours=i + 1),
            )
        _make_enabled_schedule(
            session,
            profile_name="Disabled profile",
            label="Disabled label",
            next_run_at=now + timedelta(minutes=1),  # soonest, but disabled
            enabled=False,
        )

    page = authed_client.get("/", headers={"accept": "text/html"})
    text = page.text
    assert page.status_code == 200

    # Disabled schedule never surfaces even though it is soonest (FR-003).
    assert "Disabled label" not in text
    # At most 5 enabled rows: the 6th-soonest ("Upcoming 5") is dropped.
    assert "Upcoming 0" in text
    assert "Upcoming 4" in text
    assert "Upcoming 5" not in text
    # Each row links to the Schedules page (FR-004).
    assert 'href="/schedules"' in text


def test_home_upcoming_schedules_empty_state_renders(authed_client):
    page = authed_client.get("/", headers={"accept": "text/html"})
    assert page.status_code == 200
    # No schedules → the empty-state string renders, no error (FR-006).
    assert t("dashboard.upcoming_schedules_none") in page.text

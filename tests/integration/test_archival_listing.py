"""Integration tests: archived rows (archival.py) are excluded from the
default history/schedules/credential-check listings, and reappear with
`include_archived=true` — covering the three tables named in the
archivation request (scan history, scheduled tasks, credential-check
history)."""
from __future__ import annotations

from datetime import timedelta

from asset_dashboard.db.base import session_scope
from asset_dashboard.db.models import DiscoveryRun, Schedule, ToolCheckRun, utcnow


def test_history_api_excludes_archived_runs_by_default(authed_client):
    with session_scope() as session:
        session.add(DiscoveryRun(started_at=utcnow(), archived=False))
        session.add(DiscoveryRun(started_at=utcnow() - timedelta(days=1), archived=True))

    visible = authed_client.get("/api/history").json()
    assert len(visible) == 1

    with_archived = authed_client.get("/api/history?include_archived=true").json()
    assert len(with_archived) == 2


def test_history_page_archived_toggle_link(authed_client):
    with session_scope() as session:
        session.add(DiscoveryRun(started_at=utcnow() - timedelta(days=1), archived=True))

    page = authed_client.get("/history", headers={"accept": "text/html"})
    assert page.status_code == 200
    assert "include_archived=true" in page.text

    page_with_archived = authed_client.get(
        "/history?include_archived=true", headers={"accept": "text/html"}
    )
    assert page_with_archived.status_code == 200


def test_credential_check_run_wires_archival_at_100_rows(authed_client):
    """End-to-end: once 101 ToolCheckRun rows exist, the NEXT run
    triggers archive_oldest and the oldest 50 drop off the default
    listing — confirms the runner's wiring, not just the helper. The run is
    now asynchronous (US5), so poll for it to finish before asserting."""
    import time

    from asset_dashboard.db.models import RunStatus

    with session_scope() as session:
        for i in range(100):
            session.add(
                ToolCheckRun(
                    target_scope=["10.0.0.1"],
                    port=22,
                    service="ssh",
                    started_at=utcnow() - timedelta(minutes=1000 - i),
                )
            )
        # A dictionary must exist/be chosen for the run (US2); an empty catalog
        # keeps it network-free so the run completes instantly.
        dict_id = authed_client.post(
            "/api/tools/credential-check/credentials",
            json={"service": "ssh", "vendor": "Test ssh", "credentials": []},
        ).json()["id"]

    resp = authed_client.post(
        "/api/tools/credential-check",
        json={"target_scope": ["10.10.0.5"], "port": 22, "service": "ssh", "dictionary_id": dict_id},
    )
    assert resp.status_code == 201, resp.text
    run_id = resp.json()["run_id"]

    deadline = time.time() + 3.0
    while time.time() < deadline:
        with session_scope() as session:
            if session.get(ToolCheckRun, run_id).status != RunStatus.RUNNING:
                break
        time.sleep(0.02)

    with session_scope() as session:
        assert session.query(ToolCheckRun).count() == 101
        assert session.query(ToolCheckRun).filter_by(archived=True).count() == 50
        assert session.query(ToolCheckRun).filter_by(archived=False).count() == 51


def test_credential_check_runs_api_excludes_archived_by_default(authed_client):
    with session_scope() as session:
        session.add(
            ToolCheckRun(target_scope=["10.0.0.1"], port=22, service="ssh", archived=False)
        )
        session.add(
            ToolCheckRun(target_scope=["10.0.0.2"], port=22, service="ssh", archived=True)
        )

    visible = authed_client.get("/api/tools/credential-check/runs").json()
    assert len(visible) == 1

    with_archived = authed_client.get(
        "/api/tools/credential-check/runs?include_archived=true"
    ).json()
    assert len(with_archived) == 2


def test_schedules_page_excludes_archived_by_default(authed_client):
    from asset_dashboard.db.models import DiscoveryProfile

    profile = {
        "name": "Archival test profile",
        "description": "",
        "target_scope": ["10.0.0.0/24"],
        "port_spec": "22",
        "scan_params": {},
        "extracted_fields": [],
        "compliance_settings": {},
        "cache_freshness_seconds": 3600,
    }
    created = authed_client.post("/api/profiles", json=profile).json()

    with session_scope() as session:
        p = session.get(DiscoveryProfile, created["id"])
        session.add(
            Schedule(
                profile_id=p.id,
                recurrence={"type": "interval", "seconds": 3600},
                target_scope=["10.0.0.1"],
                next_run_at=utcnow(),
                archived=True,
            )
        )

    page = authed_client.get("/schedules", headers={"accept": "text/html"})
    assert page.status_code == 200
    assert "10.0.0.1" not in page.text

    page_with_archived = authed_client.get(
        "/schedules?include_archived=true", headers={"accept": "text/html"}
    )
    assert "10.0.0.1" in page_with_archived.text

"""Contract tests for per-schedule CRUD (FR-020-FR-023, FR-028-FR-032).

Feature 003 (US6): a profile may have multiple schedules, each with its
own `target_scope` (defaulting to the profile's saved target when
omitted on create) and an optional `label`."""

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

TARGET_LESS_PROFILE = dict(PROFILE, name="Target-less nightly", target_scope=[])


def test_create_schedule_defaults_target_to_profile_target(authed_client):
    profile = authed_client.post("/api/profiles", json=PROFILE).json()
    resp = authed_client.post(
        f"/api/profiles/{profile['id']}/schedules",
        json={"recurrence": {"type": "interval", "seconds": 86400}},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["enabled"] is True
    assert body["next_run_at"] is not None
    assert body["target_scope"] == PROFILE["target_scope"]


def test_create_schedule_with_own_target_and_label(authed_client):
    profile = authed_client.post("/api/profiles", json=PROFILE).json()
    resp = authed_client.post(
        f"/api/profiles/{profile['id']}/schedules",
        json={
            "recurrence": {"type": "interval", "seconds": 3600},
            "target_scope": ["10.0.0.0/24"],
            "label": "nightly /24 sweep",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["target_scope"] == ["10.0.0.0/24"]
    assert body["label"] == "nightly /24 sweep"


def test_create_schedule_on_target_less_profile_requires_a_target(authed_client):
    profile = authed_client.post("/api/profiles", json=TARGET_LESS_PROFILE).json()
    resp = authed_client.post(
        f"/api/profiles/{profile['id']}/schedules",
        json={"recurrence": {"type": "interval", "seconds": 3600}},
    )
    assert resp.status_code == 422
    assert "target_scope" in resp.json()["error"]["fields"]


def test_create_schedule_on_target_less_profile_with_own_target_succeeds(authed_client):
    profile = authed_client.post("/api/profiles", json=TARGET_LESS_PROFILE).json()
    resp = authed_client.post(
        f"/api/profiles/{profile['id']}/schedules",
        json={
            "recurrence": {"type": "interval", "seconds": 3600},
            "target_scope": ["10.0.0.5"],
        },
    )
    assert resp.status_code == 201
    assert resp.json()["target_scope"] == ["10.0.0.5"]


def test_multiple_schedules_per_profile_allowed(authed_client):
    profile = authed_client.post("/api/profiles", json=PROFILE).json()
    first = authed_client.post(
        f"/api/profiles/{profile['id']}/schedules",
        json={"recurrence": {"type": "interval", "seconds": 3600}, "label": "hourly"},
    )
    second = authed_client.post(
        f"/api/profiles/{profile['id']}/schedules",
        json={"recurrence": {"type": "interval", "seconds": 86400}, "label": "daily"},
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]

    listed = authed_client.get(f"/api/profiles/{profile['id']}/schedules").json()
    assert len(listed) == 2


def test_list_schedules_empty_when_none_exist(authed_client):
    profile = authed_client.post("/api/profiles", json=PROFILE).json()
    resp = authed_client.get(f"/api/profiles/{profile['id']}/schedules")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_schedule_rejects_unsupported_recurrence(authed_client):
    profile = authed_client.post("/api/profiles", json=PROFILE).json()
    resp = authed_client.post(
        f"/api/profiles/{profile['id']}/schedules",
        json={"recurrence": {"type": "bogus"}},
    )
    assert resp.status_code == 422


def test_update_schedule_target_and_label(authed_client):
    profile = authed_client.post("/api/profiles", json=PROFILE).json()
    created = authed_client.post(
        f"/api/profiles/{profile['id']}/schedules",
        json={"recurrence": {"type": "interval", "seconds": 3600}},
    ).json()

    resp = authed_client.put(
        f"/api/schedules/{created['id']}",
        json={
            "recurrence": {"type": "interval", "seconds": 7200},
            "target_scope": ["192.168.1.0/24"],
            "label": "updated",
            "enabled": False,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["target_scope"] == ["192.168.1.0/24"]
    assert body["label"] == "updated"
    assert body["enabled"] is False


def test_update_schedule_rejects_invalid_target(authed_client):
    profile = authed_client.post("/api/profiles", json=PROFILE).json()
    created = authed_client.post(
        f"/api/profiles/{profile['id']}/schedules",
        json={"recurrence": {"type": "interval", "seconds": 3600}},
    ).json()

    resp = authed_client.put(
        f"/api/schedules/{created['id']}",
        json={
            "recurrence": {"type": "interval", "seconds": 3600},
            "target_scope": ["not-a-target!!"],
        },
    )
    assert resp.status_code == 422


def test_delete_schedule_removes_it(authed_client):
    profile = authed_client.post("/api/profiles", json=PROFILE).json()
    created = authed_client.post(
        f"/api/profiles/{profile['id']}/schedules",
        json={"recurrence": {"type": "interval", "seconds": 3600}},
    ).json()

    resp = authed_client.delete(f"/api/schedules/{created['id']}")
    assert resp.status_code == 204

    listed = authed_client.get(f"/api/profiles/{profile['id']}/schedules").json()
    assert listed == []


def test_update_and_delete_schedule_404_when_missing(authed_client):
    resp = authed_client.put(
        "/api/schedules/does-not-exist",
        json={"recurrence": {"type": "interval", "seconds": 3600}},
    )
    assert resp.status_code == 404
    resp = authed_client.delete("/api/schedules/does-not-exist")
    assert resp.status_code == 404


def test_schedule_from_run_copies_profile_and_target(authed_client, monkeypatch):
    from asset_dashboard.discovery import nmap_runner

    xml = (
        "<?xml version='1.0'?><nmaprun><host><status state='up'/>"
        "<address addr='10.10.0.5' addrtype='ipv4'/><ports/></host></nmaprun>"
    )

    class _FakeProcess:
        def __init__(self):
            self.returncode = 0

        def communicate(self):
            return xml, ""

        def poll(self):
            return self.returncode

        def terminate(self):
            pass

    def fake_start_nmap(
        target_scope, port_spec, scan_params, extracted_fields=None, selected_scripts=None
    ):
        return nmap_runner.NmapRunHandle(process=_FakeProcess(), command=["nmap"])

    monkeypatch.setattr(nmap_runner, "start_nmap", fake_start_nmap)

    profile = authed_client.post("/api/profiles", json=PROFILE).json()
    run_resp = authed_client.post(f"/api/profiles/{profile['id']}/runs", json={})
    run_id = run_resp.json()["run_id"]

    import time

    deadline = time.time() + 3.0
    while time.time() < deadline:
        run = authed_client.get(f"/api/runs/{run_id}").json()
        if run["status"] != "running":
            break
        time.sleep(0.02)

    resp = authed_client.post(
        f"/api/runs/{run_id}/schedule",
        json={"recurrence": {"type": "interval", "seconds": 3600}},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["profile_id"] == profile["id"]
    assert body["target_scope"] == PROFILE["target_scope"]


def test_schedule_from_run_404_when_profile_deleted(authed_client, monkeypatch):
    from asset_dashboard.discovery import nmap_runner

    xml = "<?xml version='1.0'?><nmaprun></nmaprun>"

    class _FakeProcess:
        def __init__(self):
            self.returncode = 0

        def communicate(self):
            return xml, ""

        def poll(self):
            return self.returncode

        def terminate(self):
            pass

    def fake_start_nmap(
        target_scope, port_spec, scan_params, extracted_fields=None, selected_scripts=None
    ):
        return nmap_runner.NmapRunHandle(process=_FakeProcess(), command=["nmap"])

    monkeypatch.setattr(nmap_runner, "start_nmap", fake_start_nmap)

    profile = authed_client.post("/api/profiles", json=PROFILE).json()
    run_resp = authed_client.post(f"/api/profiles/{profile['id']}/runs", json={})
    run_id = run_resp.json()["run_id"]

    import time

    deadline = time.time() + 3.0
    while time.time() < deadline:
        run = authed_client.get(f"/api/runs/{run_id}").json()
        if run["status"] != "running":
            break
        time.sleep(0.02)

    authed_client.delete(f"/api/profiles/{profile['id']}")

    resp = authed_client.post(
        f"/api/runs/{run_id}/schedule",
        json={"recurrence": {"type": "interval", "seconds": 3600}},
    )
    assert resp.status_code == 404


def test_schedule_routes_require_authentication(client):
    resp = client.get("/api/profiles/some-id/schedules")
    assert resp.status_code == 401


# --------------------------------------------------------------------------- feature 005
def test_create_schedule_accepts_once_and_interval_unit_shapes(authed_client):
    """New discovery-UI recurrence shapes are accepted (feature 005)."""
    from datetime import timedelta

    from asset_dashboard.db.models import utcnow

    profile = authed_client.post("/api/profiles", json=PROFILE).json()
    run_at = (utcnow() + timedelta(hours=1)).isoformat()
    once = authed_client.post(
        f"/api/profiles/{profile['id']}/schedules",
        json={"recurrence": {"type": "once", "run_at": run_at}},
    )
    assert once.status_code == 201
    assert once.json()["recurrence"]["type"] == "once"

    interval = authed_client.post(
        f"/api/profiles/{profile['id']}/schedules",
        json={"recurrence": {"type": "interval", "every": 3, "unit": "day"}},
    )
    assert interval.status_code == 201
    assert interval.json()["recurrence"] == {"type": "interval", "every": 3, "unit": "day"}


def test_legacy_recurrence_shapes_still_valid_and_compute(authed_client):
    """FR-014 / SC-005: legacy interval{seconds} and daily shapes remain valid
    in the engine (the credential-tool scheduler shares it)."""
    from datetime import datetime

    from asset_dashboard.scheduling.engine import compute_next_run_at, validate_recurrence

    now = datetime(2026, 10, 22, 12, 0, 0)

    legacy_interval = {"type": "interval", "seconds": 86400}
    validate_recurrence(legacy_interval, now=now)
    assert compute_next_run_at(legacy_interval, now) == datetime(2026, 10, 23, 12, 0, 0)

    legacy_daily = {"type": "daily", "hour": 2, "minute": 0}
    validate_recurrence(legacy_daily, now=now)
    assert compute_next_run_at(legacy_daily, now) == datetime(2026, 10, 23, 2, 0, 0)

    # A legacy shape is still accepted by the create route too.
    profile = authed_client.post("/api/profiles", json=PROFILE).json()
    resp = authed_client.post(
        f"/api/profiles/{profile['id']}/schedules",
        json={"recurrence": legacy_interval},
    )
    assert resp.status_code == 201


def test_tool_task_with_legacy_recurrence_still_fires(authed_client):
    """A ToolTask carrying a legacy recurrence still fires via the shared
    tick() (FR-014)."""
    from datetime import timedelta

    from asset_dashboard.db.base import session_scope
    from asset_dashboard.db.models import ToolTask, utcnow
    from asset_dashboard.scheduling.engine import tick
    from asset_dashboard.tools.credential_tool import tasks as tool_tasks

    captured = {}

    def fake_dispatch(session, task):
        captured["fired"] = task.id

        class _Run:
            id = "tool-run-1"

        return _Run()

    import asset_dashboard.scheduling.engine as engine_mod

    # dispatch_tool_task and has_running_run are imported lazily inside
    # _tick_tool_tasks, so patch them on their source module.
    orig_dispatch = tool_tasks.dispatch_tool_task
    orig_running = tool_tasks.has_running_run
    tool_tasks.dispatch_tool_task = fake_dispatch
    tool_tasks.has_running_run = lambda session, task_id: False
    try:
        with session_scope() as session:
            task = ToolTask(
                port=22,
                service="ssh",
                recurrence={"type": "interval", "seconds": 60},
                next_run_at=utcnow() - timedelta(seconds=1),
            )
            session.add(task)
            session.flush()
            task_id = task.id

        with session_scope() as session:
            started = tick(session)
        assert "tool-run-1" in started
        assert captured.get("fired") == task_id
    finally:
        tool_tasks.dispatch_tool_task = orig_dispatch
        tool_tasks.has_running_run = orig_running
        _ = engine_mod  # keep the import referenced for clarity

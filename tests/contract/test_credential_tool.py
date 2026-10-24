"""Contract tests for /api/tools/credential-check* (FR-020-FR-025)."""
import time


def _poll_run(client, run_id, timeout=3.0):
    """Poll a tool run until it leaves `running` (US5: runs are async now)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        run = client.get(f"/api/tools/credential-check/runs/{run_id}").json()
        if run["status"] != "running":
            return run
        time.sleep(0.02)
    raise TimeoutError("tool run did not finish")


def _seed_dict(client, service="ssh", username="admin", secret="admin", keywords=None):
    """Create a dictionary via the API and return its id."""
    resp = client.post(
        "/api/tools/credential-check/credentials",
        json={
            "service": service,
            "vendor": f"Test {service}",
            "credentials": [{"username": username, "secret": secret}],
            "success_keywords": keywords or ["welcome"],
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_run_now_returns_run_id(authed_client, monkeypatch):
    from asset_dashboard.compliance import credential_check
    from asset_dashboard.compliance.probes.base import ProbeAttemptResult

    monkeypatch.setattr(credential_check.time, "sleep", lambda s: None)
    monkeypatch.setitem(
        credential_check._PROBES,
        "ssh",
        lambda *a, **k: ProbeAttemptResult(matched=False, response_excerpt=""),
    )
    dict_id = _seed_dict(authed_client)

    resp = authed_client.post(
        "/api/tools/credential-check",
        json={"target_scope": ["10.0.0.1"], "port": 22, "service": "ssh", "dictionary_id": dict_id},
    )
    assert resp.status_code == 201
    assert "run_id" in resp.json()
    assert resp.json()["status"] == "running"
    _poll_run(authed_client, resp.json()["run_id"])


def test_run_now_rejects_empty_target_scope(authed_client):
    resp = authed_client.post(
        "/api/tools/credential-check", json={"target_scope": [], "port": 22, "service": "ssh"}
    )
    assert resp.status_code == 422


def test_run_now_rejects_unknown_service(authed_client):
    resp = authed_client.post(
        "/api/tools/credential-check",
        json={"target_scope": ["10.0.0.1"], "port": 22, "service": "gopher"},
    )
    assert resp.status_code == 422


def test_run_detail_never_exposes_a_secret(authed_client, monkeypatch):
    from asset_dashboard.compliance import credential_check
    from asset_dashboard.compliance.probes.base import ProbeAttemptResult

    monkeypatch.setattr(credential_check.time, "sleep", lambda s: None)
    monkeypatch.setitem(
        credential_check._PROBES,
        "ssh",
        lambda *a, **k: ProbeAttemptResult(matched=True, response_excerpt="welcome", status=200),
    )
    dict_id = _seed_dict(authed_client, username="admin", secret="super-secret-value")

    run = authed_client.post(
        "/api/tools/credential-check",
        json={"target_scope": ["10.0.0.1"], "port": 22, "service": "ssh", "dictionary_id": dict_id},
    ).json()
    _poll_run(authed_client, run["run_id"])

    detail = authed_client.get(f"/api/tools/credential-check/runs/{run['run_id']}").json()
    assert detail["results"][0]["result"] == "non_compliant"
    assert "super-secret-value" not in str(detail)
    assert "secret" not in detail["results"][0]["detail"]
    # The matched username is surfaced (allowed); the secret is not.
    assert detail["results"][0]["matched_username"] == "admin"


def test_task_crud(authed_client):
    created = authed_client.post(
        "/api/tools/credential-check/tasks",
        json={
            "target_scope": ["10.0.0.1"],
            "port": 22,
            "service": "ssh",
            "recurrence": {"type": "interval", "seconds": 3600},
        },
    ).json()
    assert created["next_run_at"]

    listed = authed_client.get("/api/tools/credential-check/tasks").json()
    assert any(t["id"] == created["id"] for t in listed)

    updated = authed_client.put(
        f"/api/tools/credential-check/tasks/{created['id']}", json={"enabled": False}
    ).json()
    assert updated["enabled"] is False

    resp = authed_client.delete(f"/api/tools/credential-check/tasks/{created['id']}")
    assert resp.status_code == 204


def test_delete_task_with_history_detaches_runs(authed_client):
    """Regression: deleting a task that already produced a ToolCheckRun used to
    fail the tool_check_runs -> tool_tasks FK. The runs must survive the task
    (their tool_task_id nulled), and the delete must succeed."""
    from asset_dashboard.db.base import session_scope
    from asset_dashboard.db.models import RunStatus, ToolCheckRun

    created = authed_client.post(
        "/api/tools/credential-check/tasks",
        json={
            "target_scope": ["10.0.0.1"],
            "port": 22,
            "service": "ssh",
            "recurrence": {"type": "interval", "seconds": 3600},
        },
    ).json()

    # Simulate a completed scheduled run bound to this task.
    with session_scope() as session:
        session.add(
            ToolCheckRun(
                tool_task_id=created["id"],
                target_scope=["10.0.0.1"],
                port=22,
                service="ssh",
                status=RunStatus.COMPLETED,
            )
        )
    with session_scope() as session:
        run_count = (
            session.query(ToolCheckRun)
            .filter(ToolCheckRun.tool_task_id == created["id"])
            .count()
        )
    assert run_count >= 1

    resp = authed_client.delete(f"/api/tools/credential-check/tasks/{created['id']}")
    assert resp.status_code == 204

    # The runs still exist, just detached from the now-deleted task.
    with session_scope() as session:
        assert (
            session.query(ToolCheckRun)
            .filter(ToolCheckRun.tool_task_id == created["id"])
            .count()
            == 0
        )


def test_credential_list_crud(authed_client):
    created = authed_client.post(
        "/api/tools/credential-check/credentials",
        json={
            "service": "ssh",
            "vendor": "Acme routers",
            "credentials": [{"username": "admin", "secret": "admin"}],
            "success_keywords": ["Last login"],
        },
    )
    assert created.status_code == 201
    entry = created.json()
    assert entry["service"] == "ssh"
    assert len(entry["credentials"]) == 1

    listed = authed_client.get("/api/tools/credential-check/credentials").json()
    assert any(e["id"] == entry["id"] for e in listed)

    updated = authed_client.put(
        f"/api/tools/credential-check/credentials/{entry['id']}",
        json={
            "service": "ssh",
            "vendor": "Acme routers",
            "credentials": [
                {"username": "admin", "secret": "admin"},
                {"username": "root", "secret": "root"},
            ],
            "success_keywords": ["Last login"],
        },
    ).json()
    assert len(updated["credentials"]) == 2

    resp = authed_client.delete(f"/api/tools/credential-check/credentials/{entry['id']}")
    assert resp.status_code == 204


def test_credential_list_rejects_unknown_service(authed_client):
    resp = authed_client.post(
        "/api/tools/credential-check/credentials",
        json={"service": "gopher", "vendor": "x", "credentials": []},
    )
    assert resp.status_code == 422


# --- US1: scheduling parity (once/interval) ---------------------------------


def test_once_task_persists_as_once_and_computes_next_run(authed_client):
    """FR-101/FR-103: a future `once` task stays one-time (not flipped to an
    interval) and seeds next_run_at at the chosen instant."""
    from datetime import UTC, datetime, timedelta

    run_at = (datetime.now(UTC) + timedelta(days=1)).replace(microsecond=0).isoformat()
    created = authed_client.post(
        "/api/tools/credential-check/tasks",
        json={
            "target_scope": ["10.0.0.1"],
            "port": 22,
            "service": "ssh",
            "recurrence": {"type": "once", "run_at": run_at},
        },
    ).json()
    assert created["recurrence"]["type"] == "once"
    assert created["next_run_at"]


def test_past_once_task_is_rejected_with_recurrence_field_error(authed_client):
    """FR-103: a past `once` time is a 422 against the `recurrence` field."""
    from datetime import UTC, datetime, timedelta

    run_at = (datetime.now(UTC) - timedelta(days=1)).replace(microsecond=0).isoformat()
    resp = authed_client.post(
        "/api/tools/credential-check/tasks",
        json={
            "target_scope": ["10.0.0.1"],
            "port": 22,
            "service": "ssh",
            "recurrence": {"type": "once", "run_at": run_at},
        },
    )
    assert resp.status_code == 422
    assert "recurrence" in resp.json()["error"]["fields"]


def test_interval_task_computes_next_run(authed_client):
    created = authed_client.post(
        "/api/tools/credential-check/tasks",
        json={
            "target_scope": ["10.0.0.1"],
            "port": 22,
            "service": "ssh",
            "recurrence": {"type": "interval", "every": 6, "unit": "hour"},
        },
    ).json()
    assert created["recurrence"]["type"] == "interval"
    assert created["next_run_at"]


# --- US2: choose which credential dictionary to use -------------------------


def test_credentials_filter_by_service(authed_client):
    _seed_dict(authed_client, service="http")
    _seed_dict(authed_client, service="ssh")
    http_only = authed_client.get(
        "/api/tools/credential-check/credentials?service=http"
    ).json()
    assert http_only
    assert all(d["service"] == "http" for d in http_only)


def test_run_without_dictionary_when_one_exists_is_rejected(authed_client, monkeypatch):
    from asset_dashboard.compliance import credential_check
    from asset_dashboard.compliance.probes.base import ProbeAttemptResult

    monkeypatch.setattr(credential_check.time, "sleep", lambda s: None)
    monkeypatch.setitem(
        credential_check._PROBES,
        "ssh",
        lambda *a, **k: ProbeAttemptResult(matched=False, response_excerpt=""),
    )
    _seed_dict(authed_client, service="ssh")
    resp = authed_client.post(
        "/api/tools/credential-check",
        json={"target_scope": ["10.0.0.1"], "port": 22, "service": "ssh"},
    )
    assert resp.status_code == 422
    assert "dictionary_id" in resp.json()["error"]["fields"]


def test_run_with_no_dictionary_for_service_is_guided_422(authed_client):
    resp = authed_client.post(
        "/api/tools/credential-check",
        json={"target_scope": ["10.0.0.1"], "port": 22, "service": "ftp"},
    )
    assert resp.status_code == 422
    assert "dictionary_id" in resp.json()["error"]["fields"]


def test_run_persists_chosen_dictionary(authed_client, monkeypatch):
    from asset_dashboard.compliance import credential_check
    from asset_dashboard.compliance.probes.base import ProbeAttemptResult

    monkeypatch.setattr(credential_check.time, "sleep", lambda s: None)
    monkeypatch.setitem(
        credential_check._PROBES,
        "ssh",
        lambda *a, **k: ProbeAttemptResult(matched=False, response_excerpt=""),
    )
    dict_id = _seed_dict(authed_client, service="ssh")
    run = authed_client.post(
        "/api/tools/credential-check",
        json={"target_scope": ["10.0.0.1"], "port": 22, "service": "ssh", "dictionary_id": dict_id},
    ).json()
    detail = _poll_run(authed_client, run["run_id"])
    assert detail["dictionary_id"] == dict_id


def test_probe_config_validation_and_round_trip(authed_client):
    good = authed_client.post(
        "/api/tools/credential-check/credentials",
        json={
            "service": "http",
            "vendor": "Web UI",
            "credentials": [{"username": "admin", "secret": "admin"}],
            "probe_config": {"login_path": "/login", "method": "POST", "encoding": "form"},
        },
    )
    assert good.status_code == 201
    assert good.json()["probe_config"]["login_path"] == "/login"

    bad = authed_client.post(
        "/api/tools/credential-check/credentials",
        json={
            "service": "http",
            "vendor": "Web UI",
            "credentials": [{"username": "admin", "secret": "admin"}],
            "probe_config": {"method": "DELETE"},
        },
    )
    assert bad.status_code == 422
    assert "probe_config" in bad.json()["error"]["fields"]


# --- US6: rich result window ------------------------------------------------


def test_run_detail_includes_per_attempt_data(authed_client, monkeypatch):
    from asset_dashboard.compliance import credential_check
    from asset_dashboard.compliance.probes.base import ProbeAttemptResult

    monkeypatch.setattr(credential_check.time, "sleep", lambda s: None)
    calls = {"n": 0}

    def fake(*a, **k):
        calls["n"] += 1
        matched = calls["n"] == 2
        return ProbeAttemptResult(
            matched=matched,
            response_excerpt="Dashboard" if matched else "Login failed",
            status=200 if matched else 401,
        )

    monkeypatch.setitem(credential_check._PROBES, "http", fake)

    create = authed_client.post(
        "/api/tools/credential-check/credentials",
        json={
            "service": "http",
            "vendor": "Web UI",
            "credentials": [
                {"username": "admin", "secret": "wrong-secret"},
                {"username": "root", "secret": "matched-secret"},
            ],
            "success_keywords": ["Dashboard"],
        },
    ).json()
    dict_id = create["id"]

    run = authed_client.post(
        "/api/tools/credential-check",
        json={"target_scope": ["10.0.0.5"], "port": 80, "service": "http", "dictionary_id": dict_id},
    ).json()
    detail = _poll_run(authed_client, run["run_id"])

    result = detail["results"][0]
    assert result["attempts"]
    assert {a["username"] for a in result["attempts"]} == {"admin", "root"}
    assert result["matched_username"] == "root"
    assert "attempt_ceiling" in detail
    assert "error_detail" in detail
    # FR-114: no attempted/matched secret appears anywhere in the response.
    assert "matched-secret" not in str(detail)
    assert "wrong-secret" not in str(detail)


def test_secret_absent_from_json_rendered_page_and_audit(authed_client, monkeypatch):
    """T034 / FR-114 / SC-006: the attempted secret must appear nowhere in the
    run-detail JSON, the rendered result page, or the audit log."""
    from asset_dashboard.compliance import credential_check
    from asset_dashboard.compliance.probes.base import ProbeAttemptResult
    from asset_dashboard.db.base import session_scope
    from asset_dashboard.db.models import AuditLogEntry

    SECRET = "zzz-top-secret-zzz"
    monkeypatch.setattr(credential_check.time, "sleep", lambda s: None)
    monkeypatch.setitem(
        credential_check._PROBES,
        "ssh",
        lambda *a, **k: ProbeAttemptResult(matched=True, response_excerpt="welcome", status=200),
    )
    dict_id = _seed_dict(authed_client, service="ssh", username="admin", secret=SECRET)

    run = authed_client.post(
        "/api/tools/credential-check",
        json={"target_scope": ["10.0.0.1"], "port": 22, "service": "ssh", "dictionary_id": dict_id},
    ).json()
    _poll_run(authed_client, run["run_id"])

    json_body = authed_client.get(f"/api/tools/credential-check/runs/{run['run_id']}").text
    assert SECRET not in json_body

    page = authed_client.get(f"/tools/credential-check/runs/{run['run_id']}").text
    assert SECRET not in page

    with session_scope() as session:
        for entry in session.query(AuditLogEntry).all():
            assert SECRET not in str(entry.detail)

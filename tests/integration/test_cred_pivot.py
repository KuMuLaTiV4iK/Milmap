"""Integration test for User Story 2 (feature 009): select hosts on a run's
results and pivot into the credential tool, pre-filled with those addresses.

- the results page carries the "Check credentials on selected" action, which
  navigates to /tools/credential-check (with the selected targets);
- the credential-tool page honors ?targets= and carries the pre-fill wiring;
- a check launched from those targets runs under the unchanged central guard
  (attempt ceiling / cooldown) and is recorded in the audit log (SC-002,
  SC-006, FR-007/009). The pivot introduces no new attempt path.
"""
from asset_dashboard.compliance import credential_check
from asset_dashboard.compliance.probes.base import ProbeAttemptResult
from asset_dashboard.db.base import session_scope
from asset_dashboard.db.models import AuditEventType, AuditLogEntry, DefaultCredentialEntry
from tests.contract.test_runs import _patch_successful_scan, _poll_until_finished

PROFILE = {
    "name": "Cred-pivot source",
    "description": "",
    "target_scope": ["10.10.0.0/24"],
    "port_spec": "5060-5062",
    "scan_params": {"timing": "T3"},
    "extracted_fields": ["open_ports", "service_version"],
    "compliance_settings": {},
    "cache_freshness_seconds": 3600,
}


def _completed_run(authed_client, monkeypatch):
    _patch_successful_scan(monkeypatch)
    profile = authed_client.post("/api/profiles", json=PROFILE).json()
    resp = authed_client.post(f"/api/profiles/{profile['id']}/runs", json={})
    run_id = resp.json()["run_id"]
    _poll_until_finished(authed_client, run_id)
    return run_id


def _seed_ssh_dict(n=10):
    with session_scope() as session:
        entry = DefaultCredentialEntry(
            vendor="Test",
            service="ssh",
            credentials=[{"username": f"u{i}", "secret": f"s{i}"} for i in range(n)],
            success_keywords=["ok"],
        )
        session.add(entry)
        session.flush()
        return entry.id


def _poll_tool_run(client, run_id, timeout=3.0):
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        run = client.get(f"/api/tools/credential-check/runs/{run_id}").json()
        if run["status"] != "running":
            return run
        time.sleep(0.02)
    raise TimeoutError("tool run did not finish")


def test_results_page_has_credential_pivot_action(authed_client, monkeypatch):
    run_id = _completed_run(authed_client, monkeypatch)
    page = authed_client.get(f"/runs/{run_id}", headers={"accept": "text/html"})
    assert page.status_code == 200
    assert "Перевірити паролі на вибраних" in page.text  # run.check_credentials_selected
    assert "/tools/credential-check" in page.text
    # Selection checkboxes exist so the action has something to read.
    assert "host-checkbox" in page.text


def test_credential_tool_page_prefills_from_targets_query(authed_client):
    page = authed_client.get(
        "/tools/credential-check?targets=10.0.0.5,10.0.0.8", headers={"accept": "text/html"}
    )
    assert page.status_code == 200
    # The pre-fill wiring is present; the value is applied client-side on load.
    assert "prefillTargetsFromQuery" in page.text
    assert "run_target_scope" in page.text


def test_check_from_pivoted_targets_runs_guarded_and_is_audited(authed_client, monkeypatch):
    """SC-006/FR-007/009: a check launched with the pivoted addresses runs under
    the attempt ceiling and is recorded in the audit log."""
    monkeypatch.setattr(credential_check.time, "sleep", lambda s: None)
    monkeypatch.setitem(
        credential_check._PROBES,
        "ssh",
        lambda *a, **k: ProbeAttemptResult(matched=False, response_excerpt=""),
    )
    dict_id = _seed_ssh_dict(n=3)

    resp = authed_client.post(
        "/api/tools/credential-check",
        json={
            "target_scope": ["10.0.0.5", "10.0.0.8"],
            "port": 22,
            "service": "ssh",
            "dictionary_id": dict_id,
        },
    )
    assert resp.status_code == 201
    detail = _poll_tool_run(authed_client, resp.json()["run_id"])
    assert detail["status"] == "completed"
    # Bounded by the dictionary size (the default ceiling) — the guard is intact.
    assert detail["results"][0]["attempts_made"] == 3

    with session_scope() as session:
        count = (
            session.query(AuditLogEntry).filter_by(event_type=AuditEventType.TOOL_CHECK).count()
        )
        assert count >= 1

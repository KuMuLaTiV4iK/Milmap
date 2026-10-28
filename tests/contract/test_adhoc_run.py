"""Contract tests for the feature-009 ad-hoc run endpoint
POST /api/runs/ad-hoc — a fully editable one-off scan that runs WITHOUT
persisting a DiscoveryProfile.

As elsewhere, `nmap` is monkeypatched with a fake process.
"""

from asset_dashboard.discovery import nmap_runner
from tests.contract.test_runs import SAMPLE_XML, _FakeProcess, _poll_until_finished


def _patch(monkeypatch, captured=None):
    def fake_start_nmap(
        target_scope, port_spec, scan_params, extracted_fields=None, selected_scripts=None
    ):
        if captured is not None:
            captured.append(
                {
                    "target_scope": target_scope,
                    "port_spec": port_spec,
                    "scan_params": scan_params,
                    "selected_scripts": selected_scripts,
                }
            )
        return nmap_runner.NmapRunHandle(
            process=_FakeProcess(stdout=SAMPLE_XML, returncode=0), command=["nmap"]
        )

    monkeypatch.setattr(nmap_runner, "start_nmap", fake_start_nmap)


def test_adhoc_run_launches_without_creating_a_profile(authed_client, monkeypatch):
    captured: list[dict] = []
    _patch(monkeypatch, captured)
    before = len(authed_client.get("/api/profiles").json())

    resp = authed_client.post(
        "/api/runs/ad-hoc",
        json={
            "name": "One-off sweep",
            "target_scope": ["10.10.0.5"],
            "port_spec": "22,80",
            "scan_params": {"timing": "T4"},
            "extracted_fields": ["open_ports"],
        },
    )
    assert resp.status_code == 202
    run = _poll_until_finished(authed_client, resp.json()["run_id"])
    assert run["status"] == "completed"
    # The run is recorded but not linked to any profile.
    assert run["profile_id"] is None
    assert run["params_used"]["target_scope"] == ["10.10.0.5"]
    assert run["params_used"]["port_spec"] == "22,80"
    assert run["profile_snapshot"]["name"] == "One-off sweep"
    assert captured and captured[-1]["port_spec"] == "22,80"

    # No profile was created.
    assert len(authed_client.get("/api/profiles").json()) == before


def test_adhoc_run_requires_a_target(authed_client):
    resp = authed_client.post("/api/runs/ad-hoc", json={"port_spec": "22"})
    assert resp.status_code == 422
    assert "target_scope" in resp.json()["error"]["fields"]


def test_adhoc_run_rejects_disallowed_scan_params(authed_client):
    resp = authed_client.post(
        "/api/runs/ad-hoc",
        json={"target_scope": ["10.0.0.1"], "port_spec": "22", "scan_params": {"script": "x"}},
    )
    assert resp.status_code == 422
    assert "scan_params" in resp.json()["error"]["fields"]


def test_adhoc_run_rejects_non_allowlisted_script(authed_client):
    resp = authed_client.post(
        "/api/runs/ad-hoc",
        json={
            "target_scope": ["10.0.0.1"],
            "port_spec": "22",
            "selected_scripts": ["definitely-not-allowed"],
        },
    )
    assert resp.status_code == 422
    assert "selected_scripts" in resp.json()["error"]["fields"]


def test_adhoc_run_defaults_timing_when_omitted(authed_client, monkeypatch):
    captured: list[dict] = []
    _patch(monkeypatch, captured)
    resp = authed_client.post(
        "/api/runs/ad-hoc", json={"target_scope": ["10.0.0.1"], "port_spec": "22"}
    )
    assert resp.status_code == 202
    _poll_until_finished(authed_client, resp.json()["run_id"])
    assert captured[-1]["scan_params"].get("timing") == "T3"


def test_custom_scan_page_renders(authed_client):
    page = authed_client.get("/scan", headers={"accept": "text/html"})
    assert page.status_code == 200
    assert "Почати сканування" in page.text  # scan_config.start_scan
    assert "Зберегти як профіль" in page.text  # scan_config.save_as_profile


def test_custom_scan_page_prefills_targets(authed_client):
    page = authed_client.get("/scan?targets=10.0.0.1,10.0.0.2", headers={"accept": "text/html"})
    assert page.status_code == 200
    assert "10.0.0.1, 10.0.0.2" in page.text

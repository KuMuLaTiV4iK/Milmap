"""Feature 006 — profile editor backend delta (US3, C-API-1).

POST /api/profiles/preview-command must render a complete command even with
no target (FR-008): it validates with require_target=False and substitutes a
visible placeholder token for the empty target, so the preview is never blank
or a target-only validation error. A real target renders the executable
command unchanged, and other validation errors (bad port spec) still fail.
"""

from __future__ import annotations

PLACEHOLDER = "<ціль>"

BASE = {
    "name": "Preview profile",
    "description": "",
    "scan_params": {"timing": "T3"},
    "extracted_fields": ["open_ports"],
    "selected_scripts": [],
    "compliance_settings": {},
    "cache_freshness_seconds": 3600,
}


def test_preview_with_empty_target_returns_placeholder_command(authed_client):
    body = dict(BASE, target_scope=[], port_spec="22,80,443")
    resp = authed_client.post("/api/profiles/preview-command", json=body)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["display"].startswith("nmap ")
    assert PLACEHOLDER in data["display"]
    assert "22,80,443" in data["display"]


def test_preview_with_real_target_has_no_placeholder(authed_client):
    body = dict(BASE, target_scope=["10.10.0.0/24"], port_spec="5060-5062")
    resp = authed_client.post("/api/profiles/preview-command", json=body)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "10.10.0.0/24" in data["display"]
    assert PLACEHOLDER not in data["display"]


def test_preview_with_bad_port_spec_still_fails_validation(authed_client):
    body = dict(BASE, target_scope=[], port_spec="not-a-port")
    resp = authed_client.post("/api/profiles/preview-command", json=body)
    assert resp.status_code == 422, resp.text

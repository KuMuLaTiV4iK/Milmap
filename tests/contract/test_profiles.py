"""Contract tests for /api/profiles* (FR-001-FR-014, FR-027, FR-042)."""

VOIP_PROFILE = {
    "name": "VoIP Infrastructure Audit",
    "description": "Map VoIP endpoints for firmware compliance.",
    "target_scope": ["10.10.0.0/24"],
    "port_spec": "5060-5062",
    "scan_params": {"timing": "T3"},
    "extracted_fields": ["open_ports", "service_version"],
    "selected_scripts": [],
    "compliance_settings": {"version_validity": True},
    "cache_freshness_seconds": 3600,
}


def test_create_profile_succeeds(authed_client):
    resp = authed_client.post("/api/profiles", json=VOIP_PROFILE)
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "VoIP Infrastructure Audit"
    assert body["version_token"] == 1
    assert "host_links" not in body


def test_create_profile_ignores_legacy_host_links_payload(authed_client):
    legacy = dict(VOIP_PROFILE, name="Legacy client payload")
    legacy["host_links"] = [{"label": "Manage", "url_template": "https://{host}/"}]
    resp = authed_client.post("/api/profiles", json=legacy)
    assert resp.status_code == 201
    assert "host_links" not in resp.json()


def test_create_profile_defaults_timing_to_t3_when_omitted(authed_client):
    no_timing = dict(VOIP_PROFILE, name="No timing specified", scan_params={})
    resp = authed_client.post("/api/profiles", json=no_timing)
    assert resp.status_code == 201
    assert resp.json()["scan_params"]["timing"] == "T3"


def test_create_profile_open_ports_only_is_valid(authed_client):
    open_ports_only = dict(
        VOIP_PROFILE, name="Open ports only", extracted_fields=["open_ports"]
    )
    resp = authed_client.post("/api/profiles", json=open_ports_only)
    assert resp.status_code == 201
    assert resp.json()["extracted_fields"] == ["open_ports"]


def test_create_profile_rejects_off_allowlist_script(authed_client):
    bad = dict(VOIP_PROFILE, name="Bad script", selected_scripts=["not-on-the-allowlist"])
    resp = authed_client.post("/api/profiles", json=bad)
    assert resp.status_code == 422
    assert "selected_scripts" in resp.json()["error"]["fields"]


def test_preview_command_matches_build_nmap_command(authed_client):
    resp = authed_client.post("/api/profiles/preview-command", json=VOIP_PROFILE)
    assert resp.status_code == 200
    body = resp.json()
    assert "-T3" in body["command"]
    assert "-sV" in body["command"]
    assert body["display"] == " ".join(body["command"])


def test_create_profile_rejects_malformed_target(authed_client):
    bad = dict(VOIP_PROFILE, target_scope=["not-a-target!!"])
    resp = authed_client.post("/api/profiles", json=bad)
    assert resp.status_code == 422
    assert "target_scope" in resp.json()["error"]["fields"]


def test_create_profile_rejects_disallowed_scan_param(authed_client):
    bad = dict(VOIP_PROFILE, scan_params={"raw_flags": "-sS --script vuln"})
    resp = authed_client.post("/api/profiles", json=bad)
    assert resp.status_code == 422
    assert "scan_params" in resp.json()["error"]["fields"]


def test_list_and_get_profile(authed_client):
    created = authed_client.post("/api/profiles", json=VOIP_PROFILE).json()
    listed = authed_client.get("/api/profiles").json()
    assert any(p["id"] == created["id"] for p in listed)

    fetched = authed_client.get(f"/api/profiles/{created['id']}").json()
    assert fetched["id"] == created["id"]


def test_update_profile_with_current_version_succeeds(authed_client):
    created = authed_client.post("/api/profiles", json=VOIP_PROFILE).json()
    update_body = dict(
        VOIP_PROFILE, name="VoIP Audit (updated)", version_token=created["version_token"]
    )
    resp = authed_client.put(f"/api/profiles/{created['id']}", json=update_body)
    assert resp.status_code == 200
    assert resp.json()["name"] == "VoIP Audit (updated)"
    assert resp.json()["version_token"] == 2


def test_update_profile_with_stale_version_returns_409(authed_client):
    created = authed_client.post("/api/profiles", json=VOIP_PROFILE).json()
    # First update succeeds, bumping version to 2.
    authed_client.put(
        f"/api/profiles/{created['id']}",
        json=dict(VOIP_PROFILE, name="first edit", version_token=created["version_token"]),
    )
    # Second update still targets the now-stale original version_token (1).
    stale_update = dict(VOIP_PROFILE, name="second edit", version_token=created["version_token"])
    resp = authed_client.put(f"/api/profiles/{created['id']}", json=stale_update)
    assert resp.status_code == 409


def test_duplicate_profile_creates_independent_copy(authed_client):
    created = authed_client.post("/api/profiles", json=VOIP_PROFILE).json()
    dup = authed_client.post(f"/api/profiles/{created['id']}/duplicate").json()
    assert dup["id"] != created["id"]
    assert dup["name"] != created["name"]

    # Editing the duplicate must not affect the original.
    authed_client.put(
        f"/api/profiles/{dup['id']}",
        json=dict(VOIP_PROFILE, name="duplicate edited", version_token=dup["version_token"]),
    )
    original = authed_client.get(f"/api/profiles/{created['id']}").json()
    assert original["name"] == VOIP_PROFILE["name"]


def test_delete_profile_removes_it_from_listing(authed_client):
    created = authed_client.post("/api/profiles", json=VOIP_PROFILE).json()
    resp = authed_client.delete(f"/api/profiles/{created['id']}")
    assert resp.status_code == 204
    listed = authed_client.get("/api/profiles").json()
    assert all(p["id"] != created["id"] for p in listed)


def test_profile_routes_require_authentication(client):
    resp = client.get("/api/profiles")
    assert resp.status_code == 401


def test_create_profile_with_empty_target_scope_succeeds(authed_client):
    """FR-003a: a profile may be saved without a target."""
    target_less = dict(VOIP_PROFILE, name="Target-less profile", target_scope=[])
    resp = authed_client.post("/api/profiles", json=target_less)
    assert resp.status_code == 201
    assert resp.json()["target_scope"] == []


def test_update_profile_to_empty_target_scope_succeeds(authed_client):
    created = authed_client.post("/api/profiles", json=VOIP_PROFILE).json()
    update_body = dict(VOIP_PROFILE, target_scope=[], version_token=created["version_token"])
    resp = authed_client.put(f"/api/profiles/{created['id']}", json=update_body)
    assert resp.status_code == 200
    assert resp.json()["target_scope"] == []


def test_create_profile_with_non_empty_invalid_target_scope_still_rejected(authed_client):
    """A present (non-empty) target is still fully validated even though
    an empty one is now allowed."""
    bad = dict(VOIP_PROFILE, name="Still invalid", target_scope=["not-a-target!!"])
    resp = authed_client.post("/api/profiles", json=bad)
    assert resp.status_code == 422
    assert "target_scope" in resp.json()["error"]["fields"]

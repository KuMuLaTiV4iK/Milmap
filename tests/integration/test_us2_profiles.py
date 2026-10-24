"""Integration test for User Story 2: create/edit/duplicate/delete flow.
See spec.md US2 Independent Test: create "VoIP Infrastructure Audit",
edit its parameters/fields, duplicate it, delete it — verifying each
change persists and is reflected in the profile list."""

VOIP_PROFILE = {
    "name": "VoIP Infrastructure Audit",
    "description": "Map VoIP endpoints for firmware compliance.",
    "target_scope": ["10.10.0.0/24"],
    "port_spec": "5060-5062",
    "scan_params": {"timing": "T3"},
    "extracted_fields": ["open_ports", "service_version"],
    "compliance_settings": {"version_validity": True},
    "cache_freshness_seconds": 3600,
}


def test_full_profile_lifecycle(authed_client):
    client = authed_client

    # Create.
    created = client.post("/api/profiles", json=VOIP_PROFILE).json()
    assert created["name"] == "VoIP Infrastructure Audit"

    # Appears in the list.
    listing = client.get("/api/profiles").json()
    assert any(p["id"] == created["id"] for p in listing)

    # Edit: widen the port range and change the discovery-time tuning.
    edited_body = dict(
        VOIP_PROFILE,
        port_spec="5060-5070",
        scan_params={"timing": "T4"},
        version_token=created["version_token"],
    )
    edited = client.put(f"/api/profiles/{created['id']}", json=edited_body).json()
    assert edited["port_spec"] == "5060-5070"
    assert edited["scan_params"]["timing"] == "T4"

    # Duplicate: independent copy, original untouched.
    duplicate = client.post(f"/api/profiles/{created['id']}/duplicate").json()
    assert duplicate["id"] != edited["id"]
    assert duplicate["port_spec"] == "5060-5070"  # copied from the edited state

    listing_after_duplicate = client.get("/api/profiles").json()
    assert len(listing_after_duplicate) == 2

    # Delete the duplicate; original remains.
    resp = client.delete(f"/api/profiles/{duplicate['id']}")
    assert resp.status_code == 204

    final_listing = client.get("/api/profiles").json()
    assert len(final_listing) == 1
    assert final_listing[0]["id"] == created["id"]


def test_html_pages_render(authed_client):
    client = authed_client
    created = client.post("/api/profiles", json=VOIP_PROFILE).json()

    resp = client.get("/profiles")
    assert resp.status_code == 200
    assert "VoIP Infrastructure Audit" in resp.text

    resp = client.get("/profiles/new")
    assert resp.status_code == 200

    resp = client.get(f"/profiles/{created['id']}")
    assert resp.status_code == 200
    assert "VoIP Infrastructure Audit" in resp.text

    resp = client.get("/profiles/does-not-exist")
    assert resp.status_code == 404

"""Integration test for User Story 2: profile duplicate/delete update the
profiles list in place via HTMX, no manual reload; a failed mutation
leaves the view consistent with server state (FR-006-FR-008)."""

PROFILE = {
    "name": "Dynamic UI test profile",
    "description": "",
    "target_scope": ["10.10.0.0/24"],
    "port_spec": "22",
    "scan_params": {"timing": "T3"},
    "extracted_fields": ["open_ports"],
    "compliance_settings": {},
    "cache_freshness_seconds": 3600,
}


def test_duplicate_via_hx_request_returns_row_fragment_not_full_page(authed_client):
    profile = authed_client.post("/api/profiles", json=PROFILE).json()
    resp = authed_client.post(
        f"/api/profiles/{profile['id']}/duplicate", headers={"HX-Request": "true"}
    )
    assert resp.status_code == 201
    assert "<tr" in resp.text
    assert "<html" not in resp.text.lower()
    assert f"{PROFILE['name']} (copy)" in resp.text


def test_duplicate_without_hx_request_still_returns_json(authed_client):
    profile = authed_client.post("/api/profiles", json=PROFILE).json()
    resp = authed_client.post(f"/api/profiles/{profile['id']}/duplicate")
    assert resp.status_code == 201
    assert resp.json()["name"] == f"{PROFILE['name']} (copy)"


def test_delete_via_hx_request_returns_empty_body_204(authed_client):
    profile = authed_client.post("/api/profiles", json=PROFILE).json()
    resp = authed_client.delete(f"/api/profiles/{profile['id']}", headers={"HX-Request": "true"})
    assert resp.status_code == 204
    assert resp.text == ""

    listed = authed_client.get("/api/profiles").json()
    assert all(p["id"] != profile["id"] for p in listed)


def test_profiles_list_page_renders_dynamic_wiring(authed_client):
    authed_client.post("/api/profiles", json=PROFILE)
    page = authed_client.get("/profiles", headers={"accept": "text/html"})
    assert page.status_code == 200
    assert "hx-post" in page.text
    assert "hx-delete" in page.text
    assert "profiles-error" in page.text


def test_failed_delete_of_nonexistent_profile_returns_404_and_json_error(authed_client):
    resp = authed_client.delete("/api/profiles/does-not-exist", headers={"HX-Request": "true"})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"

"""Integration test for User Story 1: edit an existing profile via a
button (see spec.md US1 Independent Test): open an existing profile via
its Edit button, change fields, save -> same profile updated, no
duplicate; a stale version_token is rejected (409)."""

PROFILE = {
    "name": "Edit Me",
    "description": "",
    "target_scope": ["10.0.0.0/24"],
    "port_spec": "22",
    "scan_params": {"timing": "T3"},
    "extracted_fields": ["open_ports"],
    "compliance_settings": {},
    "cache_freshness_seconds": 3600,
}


def test_profiles_list_shows_edit_button_per_row(authed_client):
    authed_client.post("/api/profiles", json=PROFILE)
    page = authed_client.get("/profiles")
    assert page.status_code == 200
    assert "Edit Me" in page.text
    assert "/profiles/" in page.text  # the Edit link target


def test_edit_button_loads_prefilled_editor(authed_client):
    created = authed_client.post("/api/profiles", json=PROFILE).json()
    page = authed_client.get(f"/profiles/{created['id']}")
    assert page.status_code == 200
    assert "Edit Me" in page.text


def test_put_updates_in_place_no_duplicate(authed_client):
    created = authed_client.post("/api/profiles", json=PROFILE).json()
    update = dict(PROFILE, name="Edited Name", version_token=created["version_token"])
    resp = authed_client.put(f"/api/profiles/{created['id']}", json=update)
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]
    assert resp.json()["version_token"] == 2

    listing = authed_client.get("/api/profiles").json()
    assert len(listing) == 1
    assert listing[0]["name"] == "Edited Name"


def test_stale_version_token_is_rejected_with_409(authed_client):
    created = authed_client.post("/api/profiles", json=PROFILE).json()
    authed_client.put(
        f"/api/profiles/{created['id']}",
        json=dict(PROFILE, name="first edit", version_token=created["version_token"]),
    )
    stale = authed_client.put(
        f"/api/profiles/{created['id']}",
        json=dict(PROFILE, name="stale edit", version_token=created["version_token"]),
    )
    assert stale.status_code == 409

    # The stored profile is unchanged by the rejected stale update.
    current = authed_client.get(f"/api/profiles/{created['id']}").json()
    assert current["name"] == "first edit"

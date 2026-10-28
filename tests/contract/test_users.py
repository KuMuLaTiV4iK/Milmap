"""Contract tests for /api/users* (FR-026-FR-034)."""


def test_new_users_default_to_operator_role(admin_client):
    resp = admin_client.post("/api/users", json={"username": "newop", "password": "x" * 25})
    assert resp.status_code == 201
    assert resp.json()["role"] == "operator"


def test_admin_can_create_operator_and_admin_users(admin_client):
    resp = admin_client.post(
        "/api/users",
        json={"username": "another_admin", "password": "x" * 25, "role": "administrator"},
    )
    assert resp.status_code == 201
    assert resp.json()["role"] == "administrator"


def test_operator_cannot_manage_users(authed_client):
    resp = authed_client.get("/api/users")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"

    resp2 = authed_client.post("/api/users", json={"username": "x", "password": "x" * 25})
    assert resp2.status_code == 403


def test_demoting_the_last_active_admin_is_rejected(admin_client, bootstrap_admin_account):
    # admin_client's own account is the only active admin.
    listing = admin_client.get("/api/users").json()
    [self_account] = [u for u in listing if u["role"] == "administrator"]

    resp = admin_client.put(f"/api/users/{self_account['id']}", json={"role": "operator"})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "last_admin"


def test_deactivating_the_last_active_admin_is_rejected(admin_client):
    listing = admin_client.get("/api/users").json()
    [self_account] = [u for u in listing if u["role"] == "administrator"]

    resp = admin_client.put(f"/api/users/{self_account['id']}", json={"status": "disabled"})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "last_admin"


def test_with_two_admins_one_can_be_demoted(admin_client):
    created = admin_client.post(
        "/api/users",
        json={"username": "second_admin", "password": "x" * 25, "role": "administrator"},
    ).json()
    resp = admin_client.put(f"/api/users/{created['id']}", json={"role": "operator"})
    assert resp.status_code == 200
    assert resp.json()["role"] == "operator"


def test_reset_password_invalidates_target_session(admin_client, second_client):
    created = admin_client.post(
        "/api/users", json={"username": "victim", "password": "x" * 25}
    ).json()
    login = second_client.post("/api/auth/login", json={"username": "victim", "password": "x" * 25})
    assert login.status_code == 200

    resp = admin_client.post(
        f"/api/users/{created['id']}/reset-password", json={"new_password": "y" * 25}
    )
    assert resp.status_code == 204

    # The victim's prior session is now invalid.
    gated = second_client.get("/api/profiles")
    assert gated.status_code == 401

    # The old password no longer works; the new one does.
    old_login = second_client.post(
        "/api/auth/login", json={"username": "victim", "password": "x" * 25}
    )
    assert old_login.status_code == 401
    new_login = second_client.post(
        "/api/auth/login", json={"username": "victim", "password": "y" * 25}
    )
    assert new_login.status_code == 200

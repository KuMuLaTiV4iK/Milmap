"""Contract tests for /api/settings/security and /api/account/password (FR-032)."""


def test_get_security_settings_defaults(admin_client):
    resp = admin_client.get("/api/settings/security")
    assert resp.status_code == 200
    body = resp.json()
    assert body["password_min_length"] == 20
    assert "lockout_threshold" in body
    assert "lockout_duration_seconds" in body
    assert "session_idle_timeout_seconds" in body


def test_password_min_length_below_floor_rejected(admin_client):
    resp = admin_client.put("/api/settings/security", json={"password_min_length": 10})
    assert resp.status_code == 422
    assert "password_min_length" in resp.json()["error"]["fields"]


def test_password_min_length_can_be_raised_above_floor(admin_client):
    resp = admin_client.put("/api/settings/security", json={"password_min_length": 24})
    assert resp.status_code == 200
    assert resp.json()["password_min_length"] == 24


def test_operator_cannot_read_or_write_security_settings(authed_client):
    assert authed_client.get("/api/settings/security").status_code == 403
    resp = authed_client.put("/api/settings/security", json={"password_min_length": 25})
    assert resp.status_code == 403


def test_self_password_change_enforces_effective_min_length(admin_client, bootstrap_admin_account):
    # Raise the floor to 24, then try a 20-char new password (would have
    # passed the hardcoded default but must now fail against the raised
    # effective setting).
    admin_client.put("/api/settings/security", json={"password_min_length": 24})

    resp = admin_client.post(
        "/api/account/password",
        json={"current_password": "an-even-longer-and-stronger-password", "new_password": "x" * 20},
    )
    assert resp.status_code == 422

    resp_ok = admin_client.post(
        "/api/account/password",
        json={"current_password": "an-even-longer-and-stronger-password", "new_password": "y" * 25},
    )
    assert resp_ok.status_code == 204


def test_self_password_change_rejects_wrong_current_password(authed_client):
    resp = authed_client.post(
        "/api/account/password",
        json={"current_password": "wrong", "new_password": "z" * 25},
    )
    assert resp.status_code == 401

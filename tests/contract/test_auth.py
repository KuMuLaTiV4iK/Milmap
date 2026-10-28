"""Contract tests for /api/auth/* and /api/accounts/* (FR-001-FR-006).

Per contracts/http-api.md, every path except GET /login and
POST /api/auth/login requires an authenticated session (FR-001) — so
account management (/api/accounts/*) is exercised here as an already
signed-in operator, mirroring the real admin workflow. The very first
account on a fresh install is created out-of-band via the CLI bootstrap
helper (T022), simulated here by the `bootstrap_account` fixture.
"""


def test_unauthenticated_request_is_rejected_with_no_data(client):
    resp = client.get("/api/does-not-exist-but-is-gated", headers={"accept": "application/json"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthenticated"


def test_unauthenticated_account_creation_is_gated(client):
    resp = client.post("/api/accounts", json={"username": "alice", "password": "x" * 25})
    assert resp.status_code == 401


def test_create_account_rejects_short_password(authed_client):
    resp = authed_client.post("/api/accounts", json={"username": "alice", "password": "tooshort"})
    assert resp.status_code == 422
    assert "password" in resp.json()["error"]["fields"]


def test_create_account_accepts_policy_compliant_password(authed_client):
    resp = authed_client.post(
        "/api/accounts",
        json={"username": "alice", "password": "a-very-long-and-strong-password"},
    )
    assert resp.status_code == 201
    assert resp.json()["username"] == "alice"


def test_login_with_valid_credentials_succeeds(client, bootstrap_account):
    _id, username, password = bootstrap_account("bob")
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    assert resp.cookies.get("session_id") is not None


def test_login_with_invalid_credentials_fails(client, bootstrap_account):
    bootstrap_account("carol")
    resp = client.post("/api/auth/login", json={"username": "carol", "password": "wrong-password"})
    assert resp.status_code == 401


def test_repeated_failures_throttle_the_account(client, bootstrap_account):
    bootstrap_account("dave")
    last = None
    for _ in range(6):
        last = client.post("/api/auth/login", json={"username": "dave", "password": "wrong"})
    assert last.status_code == 429


def test_logout_invalidates_session(authed_client):
    resp = authed_client.post("/api/auth/logout")
    assert resp.status_code == 200
    # Session cookie is gone; a subsequent gated request is rejected again.
    resp2 = authed_client.get(
        "/api/does-not-exist-but-is-gated", headers={"accept": "application/json"}
    )
    assert resp2.status_code == 401


def test_change_password_rejects_short_new_password(authed_client, bootstrap_account):
    account_id, username, password = bootstrap_account("erin")
    resp = authed_client.post(
        f"/api/accounts/{account_id}/password",
        json={"current": password, "new": "short"},
    )
    assert resp.status_code == 422

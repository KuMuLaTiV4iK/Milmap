"""Integration test for User Story 1: the full access-control journey
(gate, throttle, idle timeout) — see spec.md US1 acceptance scenarios.

Feature 002 (FR-032): the idle timeout the auth gate enforces is the
*effective* `session_idle_timeout_seconds` (settings_store, admin-editable
at runtime), not a fixed value baked into the SessionStore at construction
— so this test overrides it via a SecuritySetting row rather than
mutating the store's private attribute directly.
"""
import time


def test_full_journey_gate_then_signin_then_idle_timeout(client, bootstrap_account):
    # 1. Unauthenticated: no data disclosed. The gate redirects HTML requests
    #    to /login (disable auto-follow to see the redirect itself).
    resp = client.get("/", headers={"accept": "text/html"}, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"

    # 2. Sign in.
    _id, username, password = bootstrap_account("frank")
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200

    # 3. Authenticated request succeeds against a gated API path's auth check
    #    (using the account-creation endpoint, which is gated but not 404).
    resp = client.post("/api/accounts", json={"username": "grace", "password": "x" * 25})
    assert resp.status_code == 201

    # 4. Simulate idle timeout via the effective (admin-editable) setting.
    from asset_dashboard.db.base import session_scope
    from asset_dashboard.db.models import SecuritySetting

    with session_scope() as session:
        session.add(SecuritySetting(key="session_idle_timeout_seconds", value=1))
    time.sleep(1.1)
    resp = client.post("/api/accounts", json={"username": "henry", "password": "x" * 25})
    assert resp.status_code == 401

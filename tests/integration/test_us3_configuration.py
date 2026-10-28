"""Integration test for User Story 3: Configuration area — account
security, roles & user management (see spec.md US3 Independent Test):
admin creates an Operator; the Operator can change their own password but
not manage others (403); admin can't lower min length below 20 or remove
the last admin; deactivation invalidates sessions; actions are audited.
"""


def test_full_configuration_flow(admin_client, second_client):
    # 1. Admin creates an Operator.
    created = admin_client.post(
        "/api/users", json={"username": "field_operator", "password": "x" * 25}
    ).json()
    assert created["role"] == "operator"

    # 2. The operator can sign in and change their own password.
    op_login = second_client.post(
        "/api/auth/login", json={"username": "field_operator", "password": "x" * 25}
    )
    assert op_login.status_code == 200
    pw_change = second_client.post(
        "/api/account/password",
        json={"current_password": "x" * 25, "new_password": "z" * 25},
    )
    assert pw_change.status_code == 204

    # 3. The operator cannot manage other users or settings (403), but can
    # still use ordinary profile/tool capabilities.
    assert second_client.get("/api/users").status_code == 403
    assert second_client.get("/api/settings/security").status_code == 403
    assert second_client.post("/api/nse-scripts", json={"script_id": "x"}).status_code == 403
    assert second_client.get("/api/profiles").status_code == 200

    # 4. Admin can't lower the password floor below 20.
    assert (
        admin_client.put("/api/settings/security", json={"password_min_length": 10}).status_code
        == 422
    )
    # Admin CAN raise the session idle timeout.
    resp = admin_client.put("/api/settings/security", json={"session_idle_timeout_seconds": 7200})
    assert resp.status_code == 200
    assert resp.json()["session_idle_timeout_seconds"] == 7200

    # 5. Admin can't deactivate/demote the only administrator.
    listing = admin_client.get("/api/users").json()
    [self_account] = [u for u in listing if u["role"] == "administrator"]
    assert (
        admin_client.put(
            f"/api/users/{self_account['id']}", json={"status": "disabled"}
        ).status_code
        == 409
    )

    # Deactivating the operator invalidates their session.
    operator_account = next(u for u in listing if u["username"] == "field_operator")
    deactivate = admin_client.put(
        f"/api/users/{operator_account['id']}", json={"status": "disabled"}
    )
    assert deactivate.status_code == 200
    assert second_client.get("/api/profiles").status_code == 401

    # 6. Every action above is audited — spot-check via the audit log table.
    from asset_dashboard.db.base import session_scope
    from asset_dashboard.db.models import AuditEventType, AuditLogEntry

    with session_scope() as session:
        event_types = {e.event_type for e in session.query(AuditLogEntry).all()}
    assert AuditEventType.ACCOUNT_CHANGE in event_types
    assert AuditEventType.CONFIG_CHANGE in event_types


def test_configuration_page_hides_admin_sections_from_operator(
    authed_client, second_client, bootstrap_admin_account
):
    operator_page = authed_client.get("/configuration")
    assert operator_page.status_code == 200
    assert "users-card" not in operator_page.text
    assert "security-settings-card" not in operator_page.text

    _id, username, password = bootstrap_admin_account()
    second_client.post("/api/auth/login", json={"username": username, "password": password})
    admin_page = second_client.get("/configuration")
    assert "users-card" in admin_page.text
    assert "security-settings-card" in admin_page.text

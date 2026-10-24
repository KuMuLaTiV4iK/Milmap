"""Unit tests for auth/authz.py (role gates) and settings_store/service.py
(the admin-editable security-settings floor, FR-027, FR-028, FR-032)."""
import pytest

from asset_dashboard.settings_store.service import (
    PASSWORD_MIN_LENGTH_FLOOR,
    SettingsValidationError,
    get_effective_settings,
    get_effective_value,
    update_settings,
)


def test_effective_settings_fall_back_to_config_defaults_when_unset(client):
    from asset_dashboard.db.base import session_scope

    with session_scope() as session:
        settings = get_effective_settings(session)

    assert settings["password_min_length"] == 20


def test_password_min_length_floor_is_enforced(client):
    from asset_dashboard.db.base import session_scope

    with session_scope() as session, pytest.raises(SettingsValidationError) as exc_info:
        update_settings(session, {"password_min_length": PASSWORD_MIN_LENGTH_FLOOR - 1})

    assert exc_info.value.field == "password_min_length"


def test_password_min_length_can_be_raised_and_is_read_back(client):
    from asset_dashboard.db.base import session_scope

    with session_scope() as session:
        update_settings(session, {"password_min_length": 30})

    with session_scope() as session:
        assert get_effective_value(session, "password_min_length") == 30


def test_positive_integer_settings_reject_non_positive_values(client):
    from asset_dashboard.db.base import session_scope

    with session_scope() as session, pytest.raises(SettingsValidationError):
        update_settings(session, {"lockout_threshold": 0})


def test_unknown_setting_key_rejected(client):
    from asset_dashboard.db.base import session_scope

    with session_scope() as session, pytest.raises(SettingsValidationError):
        update_settings(session, {"not_a_real_setting": 1})


def test_require_admin_rejects_operator_role(authed_client):
    # authed_client bootstraps an Operator-role account by default.
    resp = authed_client.get("/api/users")
    assert resp.status_code == 403


def test_require_admin_allows_administrator_role(admin_client):
    resp = admin_client.get("/api/users")
    assert resp.status_code == 200

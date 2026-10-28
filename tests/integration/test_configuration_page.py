"""Feature 006 — role-aware Configuration page (US5, FR-012/FR-013/FR-014).

The page is split into two hash-driven sections reached from the nav
"Конфігурація" dropdown: #account and #library.

Admin:
  - Account section: own-password + Users + Security settings
  - Library section: NSE allow-list + Version dictionary
Operator:
  - Account section: own-password only
  - Library section: Version dictionary only
No users/security/NSE controls appear in the operator DOM.
"""

from __future__ import annotations


def test_admin_configuration_groups_sections_into_account_and_library(admin_client):
    page = admin_client.get("/configuration")
    assert page.status_code == 200
    text = page.text

    # All four admin-relevant sections render.
    assert "users-card" in text
    assert "security-settings-card" in text
    assert "allowlist-card" in text
    assert "reference-versions-card" in text

    # Two hash-addressable sections exist, account before library.
    assert 'id="config-account"' in text
    assert 'id="config-library"' in text
    acc = text.index('id="config-account"')
    lib = text.index('id="config-library"')
    assert acc < lib

    # Account section holds own-password + users + security.
    assert acc < text.index("password-form") < lib
    assert acc < text.index("users-card") < lib
    assert acc < text.index("security-settings-card") < lib

    # Library section holds NSE allow-list + version dictionary.
    assert text.index("allowlist-card") > lib
    assert text.index("reference-versions-card") > lib


def test_operator_configuration_is_account_password_and_library_versions_only(authed_client):
    page = authed_client.get("/configuration")
    assert page.status_code == 200
    text = page.text

    # Both sections still exist for the operator.
    assert 'id="config-account"' in text
    assert 'id="config-library"' in text

    # Account = own-password; Library = version dictionary.
    assert "password-form" in text
    assert "reference-versions-card" in text

    # No admin controls anywhere in the operator DOM.
    assert "users-card" not in text
    assert "security-settings-card" not in text
    assert "allowlist-card" not in text

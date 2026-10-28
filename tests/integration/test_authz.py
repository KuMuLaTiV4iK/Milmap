"""Feature 006 — role gating for the relocated Configuration surface (US5).

FR-013a/C-API-2: the standalone /reference-versions page redirects to
/configuration and the nav no longer links it.
FR-015/SC-007: server-side role enforcement stays authoritative — an
operator is still denied the admin APIs (users, security, NSE) with 403,
while the operator-accessible reference-versions CRUD keeps working.
"""

from __future__ import annotations

from asset_dashboard.web.i18n import t


def test_reference_versions_page_redirects_to_configuration(authed_client):
    resp = authed_client.get("/reference-versions", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert resp.headers["location"] == "/configuration"


def test_nav_no_longer_links_reference_versions(authed_client):
    page = authed_client.get("/", headers={"accept": "text/html"})
    assert "/reference-versions" not in page.text
    assert t("nav.reference_versions") not in page.text  # "Довідник версій"


def test_operator_denied_admin_apis_but_allowed_reference_versions(authed_client):
    # Admin-only APIs stay 403 for an operator (cosmetic hiding is not the gate).
    assert authed_client.get("/api/users").status_code == 403
    assert (
        authed_client.put(
            "/api/settings/security", json={"session_idle_timeout_seconds": 7200}
        ).status_code
        == 403
    )
    assert (
        authed_client.post(
            "/api/nse-scripts", json={"script_id": "x", "safety": "safe"}
        ).status_code
        == 403
    )

    # Operator-accessible version-dictionary CRUD still works.
    assert authed_client.get("/api/reference-versions").status_code == 200
    created = authed_client.post(
        "/api/reference-versions",
        json={
            "vendor": "Acme",
            "type": "router",
            "min_version": "1.2.3",
            "note": None,
        },
    )
    assert created.status_code == 201, created.text

"""ftp, https and routeros-api are wired into the default-credential check.

All three are registered probes and allowed services. With an empty
credential catalog no probe actually runs, so a run completes without
network I/O.
"""

from __future__ import annotations

from asset_dashboard.compliance.credential_check import _PROBES, check_default_credentials
from asset_dashboard.tools.credential_tool.routes import ALLOWED_SERVICES

NEW_SERVICES = ("ftp", "https", "routeros-api")


def test_new_services_are_registered_probes():
    for service in NEW_SERVICES:
        assert service in _PROBES


def test_new_services_are_allowed():
    assert set(NEW_SERVICES) <= ALLOWED_SERVICES


def test_known_services_with_empty_catalog_are_compliant_without_network(client):
    from asset_dashboard.db.base import session_scope

    with session_scope() as session:
        for service in NEW_SERVICES:
            result = check_default_credentials(session, "10.0.0.1", 8728, service)
            assert result.result == "compliant"
            assert result.attempts_made == 0
            assert result.protocol == service


def test_run_now_accepts_each_new_service(authed_client):
    # Feature 008 (US2): a run requires a chosen dictionary for the service.
    ports = {"ftp": 21, "https": 443, "routeros-api": 8728}
    for service, port in ports.items():
        # Empty catalog ⇒ zero attempts ⇒ no network I/O, while still giving
        # the run a dictionary to select (US2 requirement).
        dict_id = authed_client.post(
            "/api/tools/credential-check/credentials",
            json={"service": service, "vendor": f"Test {service}", "credentials": []},
        ).json()["id"]
        resp = authed_client.post(
            "/api/tools/credential-check",
            json={
                "target_scope": ["10.10.0.5"],
                "port": port,
                "service": service,
                "dictionary_id": dict_id,
            },
        )
        assert resp.status_code == 201, (service, resp.text)

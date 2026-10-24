"""Feature 006 — Profiles list simplification (US4, FR-007).

The "Розклад" column is removed from the Profiles table; the remaining
columns (name, target, ports) stay.
"""
from __future__ import annotations

from asset_dashboard.web.i18n import t

PROFILE = {
    "name": "Profiles-page sample",
    "description": "",
    "target_scope": ["10.10.0.0/24"],
    "port_spec": "22",
    "scan_params": {"timing": "T3"},
    "extracted_fields": ["open_ports"],
    "compliance_settings": {},
    "cache_freshness_seconds": 3600,
}


def test_profiles_list_has_no_schedule_column(authed_client):
    authed_client.post("/api/profiles", json=PROFILE)
    page = authed_client.get("/profiles", headers={"accept": "text/html"})
    assert page.status_code == 200
    text = page.text
    # "Розклад" column header and the per-row "Запланований" marker are gone.
    # Asserted as literals because their catalog keys were deleted (T021).
    # The header check is anchored to the closing </th> so it does not match
    # any nav link.
    assert "Розклад</th>" not in text
    assert "Запланований" not in text
    # Remaining headers intact.
    assert t("profiles.col_name") in text
    assert t("profiles.col_target") in text
    assert t("profiles.col_ports") in text

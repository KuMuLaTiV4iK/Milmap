"""Feature 006 — History table simplification (US4, FR-011).

The "З кешу?" column is removed from the History table; the remaining
columns (started, profile, status, hosts) stay.
"""

from __future__ import annotations

from asset_dashboard.web.i18n import t


def test_history_has_no_cached_column(authed_client):
    page = authed_client.get("/history", headers={"accept": "text/html"})
    assert page.status_code == 200
    text = page.text
    # "З кешу?" header is gone (asserted as a literal; the key was deleted, T021).
    assert "З кешу?" not in text
    # Remaining headers intact.
    assert t("history.col_started") in text
    assert t("history.col_profile") in text
    assert t("history.col_status") in text
    assert t("history.col_hosts") in text

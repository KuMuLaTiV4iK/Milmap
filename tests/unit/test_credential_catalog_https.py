"""Regression test: a credential-check task for `https` was completing
in ~0 attempts (and so near-instantly) because the offline default-
credential catalog had no `https` entry at all — `ssh`/`http`/`sip`/
`telnet` did, `https` did not, even though `https` is a fully wired
probe. This isn't a guardrail bug (the 3-attempt/5s-cooldown guard was
always honored correctly for the services that HAD candidates) — it was
a catalog coverage gap. Confirms the seeded catalog now covers `https`
and that a real check against it makes actual (guarded) attempts."""

from __future__ import annotations

from asset_dashboard.compliance.credential_check import check_default_credentials
from asset_dashboard.config import settings
from asset_dashboard.db.base import session_scope


def test_seed_reference_loads_an_https_default_credential_entry(client):
    from asset_dashboard.db.models import DefaultCredentialEntry
    from asset_dashboard.db.seed_reference import seed

    seed()

    with session_scope() as session:
        https_entries = session.query(DefaultCredentialEntry).filter_by(service="https").all()
        assert https_entries, "expected at least one seeded https default-credential entry"
        assert any(e.credentials for e in https_entries)


def test_https_check_with_seeded_catalog_makes_real_guarded_attempts(client, monkeypatch):
    from asset_dashboard.compliance import credential_check as cc_module
    from asset_dashboard.compliance.probes.base import ProbeAttemptResult
    from asset_dashboard.db.seed_reference import seed

    seed()

    monkeypatch.setitem(
        cc_module._PROBES,
        "https",
        lambda *a, **k: ProbeAttemptResult(matched=False, response_excerpt=""),
    )

    from asset_dashboard.db.models import DefaultCredentialEntry

    sleep_calls = []
    with session_scope() as session:
        # The default ceiling is the whole dictionary (exhaustive audit,
        # constitution v2.0.0), so attempts should equal the seeded https
        # candidate count — not the legacy `credential_check_max_attempts`.
        https_candidates = sum(
            len(e.credentials)
            for e in session.query(DefaultCredentialEntry).filter_by(service="https").all()
        )
        result = check_default_credentials(
            session, "10.0.0.1", 443, "https", sleep_fn=lambda s: sleep_calls.append(s)
        )

    # Before the fix: 0 candidates -> 0 attempts -> instantly "compliant".
    # After: real candidates are tried under the same guard as every
    # other service (cooldown honored between consecutive attempts).
    assert result.attempts_made > 0
    assert result.attempts_made == https_candidates
    if result.attempts_made > 1:
        assert all(s == settings.credential_check_cooldown_seconds for s in sleep_calls)

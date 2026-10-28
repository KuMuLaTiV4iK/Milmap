"""Unit tests for the device-safety invariants (constitution Principle III
v2.0.0, FR-108-FR-111, SC-004/SC-008): the central orchestrator stops on the
first match, exhausts the chosen dictionary under a configurable ceiling
(default = dictionary size), and MUST wait at least
`credential_check_cooldown_seconds` between consecutive attempts (the
NON-NEGOTIABLE invariant). A configured ceiling below the dictionary size is
the only path to `inconclusive`.
"""

from asset_dashboard.compliance import credential_check
from asset_dashboard.compliance.credential_check import check_default_credentials
from asset_dashboard.compliance.probes.base import ProbeAttemptResult
from asset_dashboard.config import settings
from asset_dashboard.db.models import DefaultCredentialEntry


def _seed_fake_credentials(session, n: int, service: str = "fake"):
    session.add(
        DefaultCredentialEntry(
            vendor="Test Vendor",
            service=service,
            credentials=[{"username": f"u{i}", "secret": f"s{i}"} for i in range(n)],
            success_keywords=["OK-SUCCESS"],
        )
    )
    session.flush()


def test_ceiling_defaults_to_dictionary_size(client, monkeypatch):
    """Constitution v2.0.0: with no configured ceiling, the whole chosen
    dictionary is tried (exhaustive audit) — not a hard cap of 3."""
    from asset_dashboard.db.base import session_scope

    monkeypatch.setitem(
        credential_check._PROBES,
        "fake",
        lambda *a, **k: ProbeAttemptResult(matched=False, response_excerpt=""),
    )

    with session_scope() as session:
        _seed_fake_credentials(session, n=10)

    with session_scope() as session:
        result = check_default_credentials(session, "10.0.0.1", 22, "fake", sleep_fn=lambda s: None)

    assert result.attempts_made == 10  # every candidate tried, no arbitrary cap


def test_cooldown_is_honored_between_every_consecutive_attempt(client, monkeypatch):
    from asset_dashboard.db.base import session_scope

    monkeypatch.setitem(
        credential_check._PROBES,
        "fake",
        lambda *a, **k: ProbeAttemptResult(matched=False, response_excerpt=""),
    )

    n = 4
    with session_scope() as session:
        _seed_fake_credentials(session, n=n)

    sleep_calls = []
    with session_scope() as session:
        check_default_credentials(
            session, "10.0.0.1", 22, "fake", sleep_fn=lambda s: sleep_calls.append(s)
        )

    # N attempts -> N-1 cooldowns (none before the first attempt).
    assert len(sleep_calls) == n - 1
    assert all(s == settings.credential_check_cooldown_seconds for s in sleep_calls)
    assert all(s >= 5.0 for s in sleep_calls)  # the NON-NEGOTIABLE floor


def test_configured_ceiling_below_dict_size_without_match_is_inconclusive(client, monkeypatch):
    """FR-111: a configured ceiling that stops below the dictionary size with
    no match is the only remaining `inconclusive` path."""
    from asset_dashboard.db.base import session_scope

    monkeypatch.setitem(
        credential_check._PROBES,
        "fake",
        lambda *a, **k: ProbeAttemptResult(matched=False, response_excerpt=""),
    )

    with session_scope() as session:
        _seed_fake_credentials(session, n=8)

    with session_scope() as session:
        result = check_default_credentials(
            session, "10.0.0.1", 22, "fake", ceiling=3, sleep_fn=lambda s: None
        )

    assert result.result == "inconclusive"
    assert result.attempts_made == 3


def test_all_known_candidates_exhausted_without_match_is_compliant(client, monkeypatch):
    from asset_dashboard.db.base import session_scope

    monkeypatch.setitem(
        credential_check._PROBES,
        "fake",
        lambda *a, **k: ProbeAttemptResult(matched=False, response_excerpt=""),
    )

    # Fewer candidates than the cap: every known credential gets tried.
    with session_scope() as session:
        _seed_fake_credentials(session, n=max(1, settings.credential_check_max_attempts - 1))

    with session_scope() as session:
        result = check_default_credentials(session, "10.0.0.1", 22, "fake", sleep_fn=lambda s: None)

    assert result.result == "compliant"


def test_tool_check_audit_event_never_contains_a_secret(client, monkeypatch):
    """FR-024: the standalone credential tool's TOOL_CHECK audit entries
    carry only attempt counts/protocol — never the attempted secret."""
    from asset_dashboard.db.base import session_scope
    from asset_dashboard.db.models import AuditEventType, AuditLogEntry
    from asset_dashboard.tools.credential_tool.service import run_credential_check

    monkeypatch.setitem(
        credential_check._PROBES,
        "fake",
        lambda *a, **k: ProbeAttemptResult(matched=False, response_excerpt=""),
    )
    with session_scope() as session:
        session.add(
            DefaultCredentialEntry(
                vendor="Test Vendor",
                service="fake",
                credentials=[{"username": "admin", "secret": "a-very-secret-value"}],
                success_keywords=["OK-SUCCESS"],
            )
        )
        session.flush()
        run_credential_check(session, target_scope=["10.0.0.9"], port=22, service="fake")

    with session_scope() as session:
        entries = session.query(AuditLogEntry).filter_by(event_type=AuditEventType.TOOL_CHECK).all()
        assert entries
        for entry in entries:
            assert "a-very-secret-value" not in str(entry.detail)
            assert "admin" not in str(entry.detail)
            assert "secret" not in {k.lower() for k in entry.detail}


def test_allowlist_and_config_change_events_never_contain_secrets(admin_client):
    """FR-014, FR-029/031: new audit event types also go through the same
    secret-free `detail` guard as every other event (audit/log.py)."""
    from asset_dashboard.db.base import session_scope
    from asset_dashboard.db.models import AuditEventType, AuditLogEntry

    admin_client.post("/api/nse-scripts", json={"script_id": "banner"})
    admin_client.put("/api/settings/security", json={"lockout_threshold": 7})

    with session_scope() as session:
        event_types = {e.event_type for e in session.query(AuditLogEntry).all()}
        assert AuditEventType.ALLOWLIST_CHANGE in event_types
        assert AuditEventType.CONFIG_CHANGE in event_types
        forbidden_keys = {"password", "secret", "credential", "passwd"}
        for entry in session.query(AuditLogEntry).all():
            assert all(k.lower() not in forbidden_keys for k in entry.detail)


def test_constitution_invariants_hold(client, monkeypatch):
    """T036 / SC-008 / SC-002: the >=5s cooldown is still enforced between
    consecutive attempts and the ceiling defaults to the dictionary size."""
    from asset_dashboard.db.base import session_scope

    assert settings.credential_check_cooldown_seconds >= 5.0  # NON-NEGOTIABLE floor

    monkeypatch.setitem(
        credential_check._PROBES,
        "fake",
        lambda *a, **k: ProbeAttemptResult(matched=False, response_excerpt=""),
    )
    with session_scope() as session:
        _seed_fake_credentials(session, n=6)

    sleep_calls = []
    with session_scope() as session:
        result = check_default_credentials(
            session, "10.0.0.1", 22, "fake", sleep_fn=lambda s: sleep_calls.append(s)
        )

    # Default ceiling = dictionary size; cooldown honored on every gap.
    assert result.attempts_made == 6
    assert len(sleep_calls) == 5
    assert all(s >= 5.0 for s in sleep_calls)


def test_a_matching_attempt_stops_immediately_and_flags_non_compliant(client, monkeypatch):
    from asset_dashboard.db.base import session_scope

    call_count = {"n": 0}

    def fake_attempt(*args, **kwargs):
        call_count["n"] += 1
        # Match on the second candidate, never reaching a third attempt.
        return ProbeAttemptResult(matched=call_count["n"] == 2, response_excerpt="")

    monkeypatch.setitem(credential_check._PROBES, "fake", fake_attempt)

    with session_scope() as session:
        _seed_fake_credentials(session, n=10)

    with session_scope() as session:
        result = check_default_credentials(session, "10.0.0.1", 22, "fake", sleep_fn=lambda s: None)

    assert result.result == "non_compliant"
    assert result.attempts_made == 2  # stopped at the match, never tried a third
    assert call_count["n"] == 2

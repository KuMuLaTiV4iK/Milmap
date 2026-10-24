"""Unit tests for FR-036a (response-body keyword match).

The offline version-validity threshold check itself has moved to
tests/unit/test_version_threshold_check.py (V0.7 overhaul)."""
from asset_dashboard.compliance.probes.base import body_matches_success


def test_body_matches_success_is_case_insensitive_substring_match():
    assert body_matches_success("Welcome to the Dashboard!", ["dashboard"]) is True
    assert body_matches_success("Login failed", ["dashboard", "welcome"]) is False


def test_body_matches_success_requires_a_real_body_not_just_status():
    # A protocol-level "200 OK" with an EMPTY body must not match on its own
    # unless the keyword itself appears in the body (FR-036a: body match,
    # not merely a status code).
    assert body_matches_success("", ["200 OK"]) is False

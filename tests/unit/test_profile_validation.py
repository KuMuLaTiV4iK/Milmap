"""FR-001, FR-005-FR-013: scan-param allow-list + target/port validation.

Feature 002: `extracted_fields` no longer has a forced minimum (any subset,
including empty, is valid); the host-management-link capability is removed
entirely — a profile with no host link saves, no `{host}` validation runs,
and a legacy `host_links` payload is simply ignored (never read by
validate_profile at all, since the field no longer exists on it).
"""
from asset_dashboard.profiles.validation import (
    validate_extracted_fields,
    validate_port_spec,
    validate_profile,
    validate_scan_params,
    validate_selected_scripts,
    validate_target_scope,
)


def test_valid_target_scope_entries_accepted():
    assert validate_target_scope(["10.0.0.0/24", "10.0.1.1", "10.0.2.1-10.0.2.50"]) is None


def test_malformed_target_rejected():
    assert validate_target_scope(["not-an-ip-or-cidr!!"]) is not None
    assert validate_target_scope([]) is not None


def test_valid_port_spec_accepted():
    assert validate_port_spec("5060-5062") is None
    assert validate_port_spec("22,80,443") is None


def test_malformed_port_spec_rejected():
    assert validate_port_spec("not-a-port") is not None
    assert validate_port_spec("") is not None


def test_allowed_scan_params_accepted():
    params = {"timing": "T3", "max_rate": 100}
    assert validate_scan_params(params) is None


def test_disallowed_scan_param_rejected():
    # A raw/free-form nmap flag must never reach validation as "allowed" —
    # this is the command-injection guard (FR-011).
    err = validate_scan_params({"raw_flags": "-sS --script vuln"})
    assert err is not None
    assert "raw_flags" in err


def test_service_detection_is_no_longer_a_scan_param():
    # Collapsed into extracted_fields (service_version) per research.md §3.
    assert validate_scan_params({"service_detection": True}) is not None


def test_invalid_timing_value_rejected():
    assert validate_scan_params({"timing": "T9"}) is not None


def test_extracted_fields_any_subset_is_valid_including_empty():
    assert validate_extracted_fields(["open_ports", "service_version"]) is None
    assert validate_extracted_fields(["open_ports"]) is None
    assert validate_extracted_fields(["service_version"]) is None
    assert validate_extracted_fields([]) is None


def test_extracted_fields_rejects_unknown_field():
    assert validate_extracted_fields(["not_a_real_field"]) is not None


def test_selected_scripts_must_be_on_the_allowlist():
    assert validate_selected_scripts(["banner"], {"banner", "mikrotik-routeros-version"}) is None
    assert validate_selected_scripts(["not-allowed"], {"banner"}) is not None


def test_validate_profile_aggregates_field_errors():
    errors = validate_profile(
        {
            "name": "",
            "target_scope": [],
            "port_spec": "bad",
            "scan_params": {"raw_flags": "-sS"},
            "extracted_fields": ["bogus"],
        }
    )
    assert set(errors) == {
        "name",
        "target_scope",
        "port_spec",
        "scan_params",
        "extracted_fields",
    }


def test_validate_profile_with_no_host_link_and_legacy_payload_saves_cleanly():
    # No host_links field at all, plus a legacy client still sending one —
    # both are valid; the capability is gone, not merely optional.
    payload = {
        "name": "VoIP Infrastructure Audit",
        "target_scope": ["10.10.0.0/24"],
        "port_spec": "5060-5062",
        "scan_params": {"timing": "T3"},
        "extracted_fields": ["open_ports", "service_version"],
        "host_links": [{"url_template": "no-placeholder-needed-anymore"}],
    }
    assert validate_profile(payload) == {}


def test_validate_profile_open_ports_only_is_valid():
    errors = validate_profile(
        {
            "name": "Open-ports-only sweep",
            "target_scope": ["10.10.0.0/24"],
            "port_spec": "1-1024",
            "scan_params": {"timing": "T3"},
            "extracted_fields": ["open_ports"],
        }
    )
    assert errors == {}


def test_validate_profile_voip_example_is_valid():
    errors = validate_profile(
        {
            "name": "VoIP Infrastructure Audit",
            "target_scope": ["10.10.0.0/24"],
            "port_spec": "5060-5062",
            "scan_params": {"timing": "T3"},
            "extracted_fields": ["open_ports", "service_version"],
        }
    )
    assert errors == {}


def test_validate_profile_rejects_off_allowlist_script():
    errors = validate_profile(
        {
            "name": "x",
            "target_scope": ["10.0.0.1"],
            "port_spec": "80",
            "scan_params": {},
            "extracted_fields": [],
            "selected_scripts": ["not-on-the-list"],
        },
        allowlisted_script_ids={"banner"},
    )
    assert "selected_scripts" in errors

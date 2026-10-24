"""Unit tests for nse/allowlist.py (FR-010-FR-019)."""
import pytest

from asset_dashboard.discovery.nmap_runner import build_nmap_command
from asset_dashboard.nse.allowlist import (
    DuplicateScriptIdError,
    InvalidScriptIdError,
    create_entry,
    port_scope_warning,
    seed_default_allowlist,
    validate_script_id,
)


def test_script_id_pattern_accepts_valid_ids():
    validate_script_id("mikrotik-routeros-version")
    validate_script_id("banner")
    validate_script_id("a.b_c-1")


def test_script_id_pattern_rejects_invalid_ids():
    for bad in ["", "Mikrotik", "-leading-dash", "with space", "../etc/passwd", "UPPER"]:
        with pytest.raises(InvalidScriptIdError):
            validate_script_id(bad)


def test_duplicate_script_id_rejected(client):
    from asset_dashboard.db.base import session_scope

    with session_scope() as session:
        create_entry(session, script_id="banner")
        with pytest.raises(DuplicateScriptIdError):
            create_entry(session, script_id="banner")


def test_seed_default_allowlist_loads_mikrotik_example(client):
    from asset_dashboard.db.base import session_scope
    from asset_dashboard.nse.allowlist import enabled_script_ids

    with session_scope() as session:
        n = seed_default_allowlist(session)
        assert n >= 1
        ids = enabled_script_ids(session)

    assert "mikrotik-routeros-version" in ids


def test_build_nmap_command_adds_script_flag_for_allowlisted_ids_only():
    # The command builder itself has no allow-list awareness (that check
    # happens at profile-save time, profiles/validation.py) — it simply
    # emits --script for whatever ids it is given, which is why save-time
    # validation is the thing that must enforce the allow-list.
    cmd = build_nmap_command(
        ["10.0.0.1"], "8291", {}, selected_scripts=["mikrotik-routeros-version"]
    )
    assert "--script" in cmd
    assert "mikrotik-routeros-version" in cmd


def test_port_scope_warning_when_expected_ports_not_in_spec(client):
    from asset_dashboard.db.base import session_scope

    with session_scope() as session:
        entry = create_entry(session, script_id="mikrotik-routeros-version", expected_ports=[8291])
        warning_present = port_scope_warning(entry, "80,443")
        warning_absent = port_scope_warning(entry, "8291")

    assert warning_present is not None
    assert warning_absent is None


def test_port_scope_warning_none_when_no_expected_ports(client):
    from asset_dashboard.db.base import session_scope

    with session_scope() as session:
        entry = create_entry(session, script_id="banner")
        assert port_scope_warning(entry, "80,443") is None

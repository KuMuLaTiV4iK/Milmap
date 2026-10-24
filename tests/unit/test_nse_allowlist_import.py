"""Unit tests for the dynamic, offline NSE bulk-import (FR-016): reads
the local nmap install's own `scripts/script.db` at call time (never a
bundled/static list, never a network fetch) and adds every script not
already on the allow-list."""
from __future__ import annotations

import pytest

from asset_dashboard.nse.allowlist import (
    NmapScriptsNotFoundError,
    _parse_script_db,
    import_from_nmap_scripts,
    resolve_nmap_scripts_dir,
)

SAMPLE_SCRIPT_DB = (
    'Entry { filename = "acarsd-info.nse", categories = { "discovery", "safe", } }\n'
    'Entry { filename = "afp-brute.nse", categories = { "brute", "intrusive", } }\n'
    'Entry { filename = "afp-path-vuln.nse", categories = { "exploit", "intrusive", "vuln", } }\n'
)


def test_parse_script_db_extracts_id_and_categories():
    parsed = _parse_script_db(SAMPLE_SCRIPT_DB)
    assert len(parsed) == 3
    by_id = {p["script_id"]: p["categories"] for p in parsed}
    assert by_id["acarsd-info"] == ["discovery", "safe"]
    assert by_id["afp-brute"] == ["brute", "intrusive"]
    assert "safe" not in by_id["afp-brute"]


def test_parse_script_db_strips_nse_extension():
    parsed = _parse_script_db('Entry { filename = "banner.nse", categories = { "safe", } }')
    assert parsed[0]["script_id"] == "banner"


def test_parse_script_db_ignores_malformed_lines():
    assert _parse_script_db("not an entry at all") == []


def test_resolve_nmap_scripts_dir_prefers_explicit_setting(tmp_path, monkeypatch):
    from asset_dashboard.config import settings as app_settings

    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    monkeypatch.setattr(app_settings, "nmap_scripts_dir", scripts_dir)

    assert resolve_nmap_scripts_dir() == scripts_dir


def test_import_creates_entries_with_safety_derived_from_catalog(client, tmp_path):
    from asset_dashboard.db.base import session_scope
    from asset_dashboard.db.models import NseScriptAllowlistEntry

    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "script.db").write_text(SAMPLE_SCRIPT_DB)

    with session_scope() as session:
        result = import_from_nmap_scripts(session, scripts_dir=scripts_dir)

    assert result == {"created": 3, "skipped": 0, "total_in_catalog": 3}

    with session_scope() as session:
        entries = {
            e.script_id: e for e in session.query(NseScriptAllowlistEntry).all()
        }
        assert entries["acarsd-info"].safety == "safe"
        assert entries["acarsd-info"].description == "discovery, safe"
        assert entries["afp-brute"].safety == "other"
        assert entries["afp-brute"].expected_ports == []
        assert all(e.enabled for e in entries.values())


def test_import_is_idempotent_and_preserves_prior_edits(client, tmp_path):
    from asset_dashboard.db.base import session_scope
    from asset_dashboard.nse.allowlist import create_entry, update_entry

    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "script.db").write_text(SAMPLE_SCRIPT_DB)

    with session_scope() as session:
        entry = create_entry(session, script_id="acarsd-info", safety="other")
        update_entry(session, entry.id, description="hand-curated note")

    with session_scope() as session:
        result = import_from_nmap_scripts(session, scripts_dir=scripts_dir)

    # Only the two NOT already present are created; the manually-curated
    # "acarsd-info" row is left untouched (safety/description preserved).
    assert result == {"created": 2, "skipped": 1, "total_in_catalog": 3}

    with session_scope() as session:
        from asset_dashboard.nse.allowlist import get_entry_by_script_id

        preserved = get_entry_by_script_id(session, "acarsd-info")
        assert preserved.safety == "other"
        assert preserved.description == "hand-curated note"


def test_import_raises_when_scripts_dir_missing(client, tmp_path):
    missing = tmp_path / "does-not-exist"
    with pytest.raises(NmapScriptsNotFoundError):
        import_from_nmap_scripts(None, scripts_dir=missing)

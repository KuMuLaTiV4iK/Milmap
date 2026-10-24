"""NSE script allow-list CRUD + validation (FR-010-FR-018).

The allow-list is the authoritative guard at scan time: `nmap_runner.
build_nmap_command` only ever receives script ids a profile has selected,
and profile save-time validation (profiles/validation.py) rejects any
`selected_scripts` id that isn't currently an *enabled* allow-list entry.
Adding a non-"safe" entry is permitted for Administrators but returns a
non-blocking warning and is audit-logged (FR-016) — the curation act
itself is deliberate and logged, not a weakening of the allow-list guard.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from asset_dashboard.config import REFERENCE_DIR, settings
from asset_dashboard.db.models import NseScriptAllowlistEntry
from asset_dashboard.profiles.validation import SCRIPT_ID_RE

SAFE = "safe"
OTHER = "other"
ALLOWED_SAFETY_VALUES = {SAFE, OTHER}

# nmap's own `scripts/script.db` catalog: one line per script, e.g.
#     Entry { filename = "acarsd-info.nse", categories = { "discovery", "safe", } }
_SCRIPT_DB_ENTRY_RE = re.compile(
    r'Entry\s*\{\s*filename\s*=\s*"([^"]+)"\s*,\s*categories\s*=\s*\{([^}]*)\}\s*\}'
)


class InvalidScriptIdError(ValueError):
    pass


class DuplicateScriptIdError(ValueError):
    pass


class NmapScriptsNotFoundError(Exception):
    """Raised when the local nmap `scripts/script.db` cannot be located —
    never falls back to a network fetch (constitution Principle I)."""


def validate_script_id(script_id: str) -> None:
    if not script_id or not SCRIPT_ID_RE.match(script_id):
        raise InvalidScriptIdError(
            "script_id must be non-empty and match ^[a-z0-9][a-z0-9._-]*$"
        )


def list_entries(session: Session) -> list[NseScriptAllowlistEntry]:
    return session.query(NseScriptAllowlistEntry).order_by(NseScriptAllowlistEntry.script_id).all()


def enabled_script_ids(session: Session) -> set[str]:
    """The set of script ids currently selectable by a profile."""
    rows = (
        session.query(NseScriptAllowlistEntry.script_id)
        .filter(NseScriptAllowlistEntry.enabled.is_(True))
        .all()
    )
    return {row[0] for row in rows}


def get_entry(session: Session, entry_id: str) -> NseScriptAllowlistEntry | None:
    return session.get(NseScriptAllowlistEntry, entry_id)


def get_entry_by_script_id(session: Session, script_id: str) -> NseScriptAllowlistEntry | None:
    return session.query(NseScriptAllowlistEntry).filter_by(script_id=script_id).one_or_none()


def scope_warnings_for_selection(
    session: Session, selected_scripts: list[str], port_spec: str
) -> list[str]:
    """Non-blocking FR-019 warnings for the given selection, e.g. a script
    whose `expected_ports` aren't in the profile's port spec."""
    warnings: list[str] = []
    for script_id in selected_scripts or []:
        entry = get_entry_by_script_id(session, script_id)
        if entry is None:
            continue
        warning = port_scope_warning(entry, port_spec)
        if warning:
            warnings.append(warning)
    return warnings


def create_entry(
    session: Session,
    *,
    script_id: str,
    description: str | None = None,
    safety: str = SAFE,
    expected_ports: list[int] | None = None,
    created_by: str | None = None,
) -> NseScriptAllowlistEntry:
    validate_script_id(script_id)
    if safety not in ALLOWED_SAFETY_VALUES:
        safety = OTHER

    existing = session.query(NseScriptAllowlistEntry).filter_by(script_id=script_id).one_or_none()
    if existing is not None:
        raise DuplicateScriptIdError(f"'{script_id}' is already on the allow-list.")

    entry = NseScriptAllowlistEntry(
        script_id=script_id,
        description=description,
        safety=safety,
        expected_ports=expected_ports or [],
        enabled=True,
        created_by=created_by,
    )
    session.add(entry)
    session.flush()
    return entry


def update_entry(
    session: Session,
    entry_id: str,
    *,
    description: str | None = None,
    safety: str | None = None,
    expected_ports: list[int] | None = None,
    enabled: bool | None = None,
) -> NseScriptAllowlistEntry | None:
    entry = get_entry(session, entry_id)
    if entry is None:
        return None
    if description is not None:
        entry.description = description
    if safety is not None and safety in ALLOWED_SAFETY_VALUES:
        entry.safety = safety
    if expected_ports is not None:
        entry.expected_ports = expected_ports
    if enabled is not None:
        entry.enabled = enabled
    session.add(entry)
    session.flush()
    return entry


def delete_entry(session: Session, entry_id: str) -> bool:
    entry = get_entry(session, entry_id)
    if entry is None:
        return False
    session.delete(entry)
    session.flush()
    return True


def port_scope_warning(entry: NseScriptAllowlistEntry, port_spec: str) -> str | None:
    """FR-019: warn (non-blocking) when an entry's `expected_ports` aren't
    present in the profile's port spec — the script may simply never run."""
    if not entry.expected_ports:
        return None
    from asset_dashboard.profiles.validation import _PORT_SPEC_RE  # noqa: PLC0415

    if not _PORT_SPEC_RE.match((port_spec or "").strip()):
        return None

    spec_ports: set[int] = set()
    for chunk in port_spec.split(","):
        chunk = chunk.strip()
        if "-" in chunk:
            start, _, end = chunk.partition("-")
            spec_ports.update(range(int(start), int(end) + 1))
        elif chunk:
            spec_ports.add(int(chunk))

    if not spec_ports.intersection(entry.expected_ports):
        return (
            f"'{entry.script_id}' expects port(s) {entry.expected_ports}, "
            f"which are not in this profile's port spec."
        )
    return None


def seed_default_allowlist(session: Session) -> int:
    """Idempotent re-seed from data/reference/nse_allowlist.json — mirrors
    db/seed_reference.py's pattern for the other offline reference data."""
    entries = json.loads((REFERENCE_DIR / "nse_allowlist.json").read_text())
    session.query(NseScriptAllowlistEntry).delete()
    for entry in entries:
        session.add(
            NseScriptAllowlistEntry(
                script_id=entry["script_id"],
                description=entry.get("description"),
                safety=entry.get("safety", SAFE),
                expected_ports=entry.get("expected_ports", []),
                enabled=True,
            )
        )
    session.flush()
    return len(entries)


def resolve_nmap_scripts_dir() -> Path | None:
    """Locate the local nmap install's `scripts/` directory — NEVER a
    network lookup (constitution Principle I). Priority: explicit
    `ASSET_DASHBOARD_NMAP_SCRIPTS_DIR` override, then the directory next
    to whatever `nmap` resolves to on PATH, then common OS install
    locations. Returns None if nothing is found."""
    if settings.nmap_scripts_dir and settings.nmap_scripts_dir.is_dir():
        return settings.nmap_scripts_dir

    nmap_path = shutil.which("nmap")
    if nmap_path:
        candidate = Path(nmap_path).resolve().parent / "scripts"
        if candidate.is_dir():
            return candidate

    for candidate in (
        Path("/usr/share/nmap/scripts"),
        Path("/usr/local/share/nmap/scripts"),
        Path("C:/Program Files (x86)/Nmap/scripts"),
        Path("C:/Program Files/Nmap/scripts"),
    ):
        if candidate.is_dir():
            return candidate

    return None


def _parse_script_db(text: str) -> list[dict]:
    """Parse nmap's `script.db` catalog format (one `Entry { filename =
    "...", categories = { ... } }` per script) into
    [{"script_id": ..., "categories": [...]}, ...]. Never guesses at a
    script's purpose/ports beyond what the catalog states."""
    parsed = []
    for filename, categories_raw in _SCRIPT_DB_ENTRY_RE.findall(text):
        script_id = filename[:-4] if filename.endswith(".nse") else filename
        categories = [c.strip().strip('"') for c in categories_raw.split(",") if c.strip()]
        parsed.append({"script_id": script_id, "categories": categories})
    return parsed


def import_from_nmap_scripts(
    session: Session, *, scripts_dir: Path | None = None, created_by: str | None = None
) -> dict:
    """Bulk-add every script in the local nmap installation's catalog to
    the allow-list (FR-016 — offline, reads local files only; no network,
    no `--script-updatedb`). `safety` is derived from the catalog's own
    "safe" category tag; `description` carries the catalog's category
    list (never a fabricated summary); `expected_ports` is left empty
    (most NSE scripts use a `portrule` function, not a fixed port list,
    so this is accurate, not a gap). Idempotent: a script_id already on
    the allow-list is left untouched (a prior manual edit — safety,
    description, expected_ports — is never overwritten)."""
    directory = scripts_dir or resolve_nmap_scripts_dir()
    if directory is None:
        raise NmapScriptsNotFoundError(
            "Could not locate the local nmap scripts directory. Set "
            "ASSET_DASHBOARD_NMAP_SCRIPTS_DIR to the nmap install's "
            "scripts/ folder (containing script.db) and retry."
        )

    db_path = directory / "script.db"
    if not db_path.is_file():
        raise NmapScriptsNotFoundError(f"{db_path} does not exist.")

    parsed = _parse_script_db(db_path.read_text(encoding="utf-8", errors="replace"))
    existing_ids = {row[0] for row in session.query(NseScriptAllowlistEntry.script_id).all()}

    created = 0
    skipped = 0
    for item in parsed:
        script_id = item["script_id"]
        if script_id in existing_ids or not SCRIPT_ID_RE.match(script_id):
            skipped += 1
            continue
        categories = item["categories"]
        session.add(
            NseScriptAllowlistEntry(
                script_id=script_id,
                description=", ".join(categories) or None,
                safety=SAFE if "safe" in categories else OTHER,
                expected_ports=[],
                enabled=True,
                created_by=created_by,
            )
        )
        existing_ids.add(script_id)
        created += 1

    session.flush()
    return {"created": created, "skipped": skipped, "total_in_catalog": len(parsed)}

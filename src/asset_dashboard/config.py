"""Application settings.

All configuration is local — no external config service, consistent with the
air-gapped deployment target (constitution Principle I).
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
REFERENCE_DIR = DATA_DIR / "reference"


class Settings(BaseSettings):
    """Runtime configuration. Overridable via environment variables (prefix ASSET_DASHBOARD_)."""

    model_config = SettingsConfigDict(env_prefix="ASSET_DASHBOARD_", env_file=None)

    # Branding / localization (feature 002)
    app_name: str = "Milmap"
    default_locale: str = "uk"

    # Persistence
    database_url: str = f"sqlite:///{(DATA_DIR / 'app.sqlite3').as_posix()}"

    # Auth / sessions (FR-001-FR-006). These are the HARD-coded fallback
    # defaults the settings_store (feature 002) reads when no admin-set
    # SecuritySetting row exists yet. `min_password_length` can never be
    # lowered below 20 by the settings store (FR-032) regardless of this
    # default.
    min_password_length: int = 20
    session_idle_timeout_seconds: int = 30 * 60  # 30 minutes
    signin_failure_threshold: int = 5
    signin_lockout_seconds: int = 15 * 60  # 15 minutes

    # Discovery / runs (FR-010, FR-021, FR-024)
    default_cache_freshness_seconds: int = 60 * 60  # 1 hour
    max_concurrent_runs: int = 4

    # Compliance — default-credential guardrails (FR-037). NON-NEGOTIABLE
    # (constitution Principle III): never raise attempts, never shrink cooldown.
    credential_check_max_attempts: int = 3
    credential_check_cooldown_seconds: float = 5.0

    # Retention (FR-026) — number of completed runs retained per profile; None = unlimited.
    history_retention_runs_per_profile: int | None = 500

    # Scheduling (FR-028-FR-032) — how often the heartbeat scans for due schedules.
    scheduler_tick_seconds: int = 30

    # Version ingestion (FR-016, FR-016a, V0.7) — pre-shared HMAC key(s) used
    # ONLY to verify an update bundle's integrity/authenticity on import.
    # Provisioned locally (no network, no PKI); never logged or returned by
    # any API/audit detail. Local file: one `key_id<TAB>hex_key` pair per
    # line. Missing file => no keys configured => every import is rejected.
    version_ingestion_keys_file: Path = DATA_DIR / "version_ingestion_keys.txt"

    # Explicit override for the local nmap install's `scripts/` directory
    # (bulk NSE allow-list import, nse/allowlist.py). Auto-detected via
    # `shutil.which("nmap")` and common OS install paths when unset.
    nmap_scripts_dir: Path | None = None


settings = Settings()


def load_version_ingestion_keys() -> dict[str, bytes]:
    """Read the local pre-shared HMAC key file: `key_id<TAB>hex_key` per
    line, blank lines and `#`-comments ignored. Returns {} if the file is
    absent (no ingestion keys provisioned on this deployment yet)."""
    path = settings.version_ingestion_keys_file
    if not path.exists():
        return {}
    keys: dict[str, bytes] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key_id, _, hex_key = line.partition("\t")
        if not key_id or not hex_key:
            continue
        keys[key_id.strip()] = bytes.fromhex(hex_key.strip())
    return keys

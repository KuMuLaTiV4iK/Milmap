"""Air-gapped integrity checks for feature 002 (constitution Principle I):
no new runtime dependency was introduced, and NSE script execution never
reaches outside the local nmap install (no --script-updatedb, no remote
fetch flags)."""

import tomllib
from pathlib import Path

from asset_dashboard.discovery.nmap_runner import build_nmap_command

REPO_ROOT = Path(__file__).resolve().parents[2]

# The dependency set already vendored for feature 001 (see plan.md
# "Primary Dependencies ... no new packages"). This is a change-detector
# by design: adding a package to pyproject.toml should be a deliberate,
# reviewed act, not a silent side effect of a future edit.
_KNOWN_DEPENDENCY_PREFIXES = {
    "fastapi",
    "uvicorn",
    "pyyaml",
    "jinja2",
    "sqlalchemy",
    "alembic",
    "apscheduler",
    "argon2-cffi",
    "pydantic",
    "pydantic-settings",
    "python-libnmap",
    "paramiko",
    "httpx",
    "itsdangerous",
    "python-multipart",
}


def test_no_new_runtime_dependency_was_added():
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    deps = pyproject["project"]["dependencies"]
    names = {dep.split("==")[0].split(">=")[0].split("[")[0].strip() for dep in deps}
    assert names == _KNOWN_DEPENDENCY_PREFIXES


def test_build_nmap_command_never_emits_a_remote_update_flag():
    cmd = build_nmap_command(
        ["10.0.0.1"], "8291", {}, selected_scripts=["mikrotik-routeros-version"]
    )
    forbidden = {"--script-updatedb", "--datadir", "--servicedb", "--versiondb"}
    assert not forbidden.intersection(cmd)

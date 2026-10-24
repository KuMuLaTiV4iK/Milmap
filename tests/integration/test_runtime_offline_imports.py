"""FR-019: the air-gapped runtime (`src/asset_dashboard/`) never imports
the staging fetcher (`tools/version_fetcher/`), and the in-runtime
ingestion package (`version_ingestion/`) specifically never imports an
HTTP client — it only verifies/imports an already-produced bundle file.

Note: `compliance/probes/http.py` legitimately uses `httpx` to probe
INTERNAL/LAN devices (default-credential checks) — that is the core
LAN-scanning function of this air-gapped tool, not an internet call, so
the HTTP-client restriction below is scoped to `version_ingestion/`
only, per research D5/contracts/fetcher-cli.md ("the web app does not
depend on" the fetcher's HTTP client).
"""
from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src" / "asset_dashboard"
VERSION_INGESTION_DIR = SRC_DIR / "version_ingestion"


def _imported_module_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                roots.add(node.module.split(".")[0])
    return roots


def test_runtime_never_imports_the_staging_fetcher():
    offenders: dict[str, set[str]] = {}
    for py_file in SRC_DIR.rglob("*.py"):
        roots = _imported_module_roots(py_file)
        hit = roots & {"tools", "version_fetcher"}
        if hit:
            offenders[str(py_file.relative_to(REPO_ROOT))] = hit

    assert not offenders, f"forbidden runtime imports found: {offenders}"


def test_version_ingestion_package_imports_no_http_client():
    offenders: dict[str, set[str]] = {}
    for py_file in VERSION_INGESTION_DIR.rglob("*.py"):
        roots = _imported_module_roots(py_file)
        hit = roots & {"httpx", "requests", "urllib3"}
        if hit:
            offenders[str(py_file.relative_to(REPO_ROOT))] = hit

    assert not offenders, f"version_ingestion/ must not import an HTTP client: {offenders}"

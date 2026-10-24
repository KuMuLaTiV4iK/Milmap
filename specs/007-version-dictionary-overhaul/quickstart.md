# Quickstart & Validation: Version Dictionary Overhaul

End-to-end validation for V0.7. Assumes the existing dev setup (Python 3.13+ venv, SQLite under `data/`). Implementation details live in `tasks.md`; this guide proves the feature works.

## Prerequisites

```powershell
# from repo root, venv active
python -m asset_dashboard.db.init          # fresh-install schema
alembic upgrade head                       # applies 0004 (schema + enumerated→threshold migration)
python -m asset_dashboard.db.seed_reference # threshold-shaped seed
pytest -q                                   # full suite green
```

## Scenario 1 — Minimum-version compliance (US1, FR-001–FR-008)

1. Ensure a threshold exists: OpenSSH `min_version = 9.0` (seeded or via Configuration Subtab 2).
2. Evaluate three detected versions (via a scan or the evaluation unit path):
   - `OpenSSH 7.4` → **non_compliant**, row highlighted orange, compliance cell shows upgrade target `OpenSSH 9.0`.
   - `OpenSSH 9.2` → **compliant**, no highlight.
   - `Acme 1.0` (no threshold) → **unknown**, no highlight.
3. Confirm the evaluation made **zero** network calls (offline).

**Automated**: `tests/unit/test_version_threshold_check.py`, `tests/unit/test_version_compare.py` (incl. `9.0`==`9.0.0`, `9.0-rc1` < `9.0`, mixed-scheme → unknown).

## Scenario 2 — Manual threshold maintenance (US2, FR-009–FR-011)

1. Sign in as an **operator**; open Configuration → Subtab 2 → version dictionary.
2. Add product `nginx` with `min_version = 1.26`; save. A later scan detecting `nginx 1.24` → non_compliant; `1.28` → compliant.
3. Edit the threshold to `1.30`; a scan detecting `1.28` now → non_compliant.
4. Confirm each edit wrote a `CONFIG_CHANGE` audit row.

**Automated**: `tests/integration/test_reference_threshold_crud.py`.

## Scenario 3 — Migration preserves coverage (FR-012, SC-008)

1. Start from a pre-V0.7 DB with enumerated OpenSSH rows (`7.*` invalid, `9.*` valid) and an invalid-only product.
2. Run `alembic upgrade head`.
3. Confirm: OpenSSH collapsed to one row `min_version = 9.0`; the invalid-only product is one row with `needs_review = true` and surfaces in the UI "needs review" list.

**Automated**: `tests/integration/test_migration_0004.py`.

## Scenario 4 — Immutable history (FR-012a, SC-009)

1. Run a scan detecting `OpenSSH 9.2` against threshold `9.0` → finding **compliant**, `detail.checked_version = 9.2`, `detail.threshold = 9.0`.
2. Raise the threshold to `9.5` and re-open the **historical** run.
3. Confirm the old finding is still **compliant** with `threshold = 9.0` (unchanged); only a *new* scan would flag `9.2` non_compliant.

**Automated**: `tests/integration/test_immutable_history.py`.

## Scenario 5 — Ingestion: fetch → bundle → import (US3, FR-014–FR-021)

**On a staging machine (internet-connected):**
```
python -m version_fetcher fetch --vendor OpenSSH \
  --source-url <captured/sample official source> --models portable \
  --extractor extractor.json --key-file ./milmap.key --key-id milmap-2026 \
  --out openssh.bundle.json
```
Confirm the bundle lists `{model:portable, version:…, status:ok}` and carries an `integrity` envelope.

**On the air-gapped deployment (as an administrator):**
1. Configuration → Subtab 2 → add a tracked source (vendor, URL, models).
2. Upload `openssh.bundle.json` → **preview**: integrity verified, diff shows `current 9.0 → incoming 9.9 (update)`.
3. **Apply** → threshold updated to `9.9` (`source=ingested`), one `CONFIG_CHANGE` `import` audit row recorded.
4. Tamper with one byte of the payload and re-upload → **rejected** (`bundle_invalid`), no threshold changed.
5. Confirm operators cannot reach the ingestion/import endpoints (403), only admins.
6. Confirm the running app made no outbound request during any step.

**Automated**: `tests/unit/test_bundle_integrity.py`, `tests/integration/test_ingestion_import.py` (verify/reject, review/apply, downgrade guard, admin-only roles).

## Success-criteria mapping

| Scenario | Criteria |
|----------|----------|
| 1 | SC-001, SC-002, SC-003 |
| 2 | SC-004, SC-006 |
| 3 | SC-008 |
| 4 | SC-009 |
| 5 | SC-005, SC-006, SC-007 + FR-019 (no runtime network) |

---

description: "Task list for Version Dictionary Overhaul (feature 007)"
---

# Tasks: Version Dictionary Overhaul

**Input**: Design documents from `specs/007-version-dictionary-overhaul/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (all present)

**Tests**: INCLUDED — the spec, quickstart, and Constitution Principle V (Testable & Independently Deliverable) call for them explicitly.

**Organization**: Grouped by the three user stories so each is independently implementable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 / US2 / US3 (Setup, Foundational, and Polish carry no story label)
- Exact file paths are given in every task.

## Path Conventions

Server-rendered single project: app under `src/asset_dashboard/`, tests under `tests/`, migrations under `migrations/versions/`, the out-of-runtime staging CLI under `tools/version_fetcher/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the two new package skeletons this feature introduces.

- [X] T001 Create the in-runtime ingestion package skeleton `src/asset_dashboard/version_ingestion/__init__.py` (config + verified import only; it MUST NOT import any HTTP client — see plan Constitution Check I).
- [X] T002 [P] Create the out-of-runtime staging CLI skeleton `tools/version_fetcher/__init__.py` and `tools/version_fetcher/extractors/__init__.py` (this package is the ONLY component allowed outbound network access; never imported by `src/asset_dashboard/`).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema, comparator, migration, and seed — required before ANY user story can be implemented or tested.

**⚠️ CRITICAL**: No user story work begins until this phase is complete.

- [X] T003 Add threshold columns to `ReferenceVersionEntry` and define the new `VersionIngestionSource` model in `src/asset_dashboard/db/models.py`, per data-model.md §1–§2. Add to `ReferenceVersionEntry`: `min_version String(128) nullable`, `model String(128) nullable indexed`, `source String(16) default "manual"` (values `manual|ingested`), `source_ref String(256) nullable`, `needs_review Boolean default false`, `updated_at DateTime default/onupdate utcnow`; retain legacy `version_match`/`status`. New `version_ingestion_sources` table: `id String(36) PK uuid`, `vendor String(128) indexed`, `source_url String(512)`, `models JSON list`, `extractor JSON default {}`, `last_import_status String(16) nullable (ok|partial|failed|null)`, `last_import_at DateTime nullable`, `last_versions JSON default {}`, `created_by String(36) FK operator_accounts.id nullable`, `created_at`/`updated_at DateTime`.
- [X] T004 Implement the deterministic SemVer-style comparator in `src/asset_dashboard/compliance/version_compare.py` per research D1 / FR-006: split on `.`, compare numeric segments left-to-right, missing trailing segments = 0 (`9.0` == `9.0.0`), a pre-release/suffix sorts BELOW its base release (`9.0-rc1` < `9.0`); expose a "not comparable" signal for unorderable or mismatched-scheme inputs (the evaluator maps that to `unknown`).
- [X] T005 Create Alembic migration `migrations/versions/0004_version_dictionary_overhaul.py` with `down_revision = "0003_schedule_target_and_label"` (depends on T003, T004). Add the T003 columns + table, then run the enumerated→threshold data transform per data-model.md §"Migration rules" / research D3: per `(vendor, product)` group set `min_version` = lowest `valid` version (comparator order; `N.*` → `N.0`), collapse to one row `source="manual"`; a group with only `invalid` rows → one row `min_version=NULL`, `needs_review=true`; emit a converted/flagged summary. Provide a best-effort `downgrade()` (documented one-way data transform; enumerated rows not reconstructed).
- [X] T006 Convert the seed data to the threshold shape: rewrite `data/reference/version_validity.json` to per-product `{vendor, product, model?, min_version, note}` and update `src/asset_dashboard/db/seed_reference.py` to load it into the new columns (depends on T003).

**Checkpoint**: Schema + comparator + migration + seed ready — user stories can begin.

---

## Phase 3: User Story 1 — Compliance by minimum-version threshold (Priority: P1) 🎯 MVP

**Goal**: Version-validity verdicts are derived by comparing the detected version to the product's `min_version` threshold (below → non-compliant, at/above → compliant, none → unknown), and each verdict is frozen into its finding (immutable history).

**Independent Test**: With threshold OpenSSH `9.0`, a scan detecting `7.4` → non_compliant (orange, upgrade target `OpenSSH 9.0`), `9.2` → compliant, a product with no threshold → unknown — all with zero network calls; raising the threshold afterward does not change the stored verdict.

### Tests for User Story 1

- [X] T007 [P] [US1] Comparator unit tests in `tests/unit/test_version_compare.py`: `9.0`==`9.0.0`, `9.0-rc1` < `9.0`, `9.10` > `9.9`, mixed-scheme/garbage → not-comparable.
- [X] T008 [P] [US1] Threshold-check unit tests in `tests/unit/test_version_threshold_check.py`: below/equal/above threshold, no-threshold → unknown, unorderable detected version → unknown, zero network calls.
- [X] T009 [P] [US1] Immutable-history integration test in `tests/integration/test_immutable_history.py` (FR-012a, SC-009): run a scan → finding stores `checked_version` + `threshold`; raise the threshold; reopen the historical run and assert the finding is byte-for-byte unchanged, only a new scan reflects the new threshold.

### Implementation for User Story 1

- [X] T010 [US1] Rewrite `src/asset_dashboard/compliance/version_check.py` to return `(result, detail)` with `result ∈ {compliant, non_compliant, unknown}` by looking up the matching `(vendor/product[/model])` threshold and comparing with `version_compare` (depends on T003, T004). `detail` carries `checked_version`, `threshold`, `matched_product`, `expected_valid` (threshold as upgrade target), and `comparison ∈ {below_threshold, at_or_above, not_comparable, no_threshold}`. No network/external lookup (FR-008).
- [X] T011 [US1] Update `src/asset_dashboard/compliance/evaluate.py` to persist the frozen `detail` from T010 into the `ComplianceFinding` and map the new result strings to `ComplianceResult` (depends on T010); ensure `expected_valid` surfaces for the feature-003 orange highlight / upgrade-target cell. Drop the old valid/invalid mapping.

**Checkpoint**: Minimum-version compliance works end-to-end on seeded/migrated data — MVP shippable.

---

## Phase 4: User Story 2 — Maintain current-version thresholds in the library (Priority: P2)

**Goal**: Operators/admins manage per-product `min_version` thresholds in Configuration Subtab 2 (replacing enumerated valid/invalid entry editing), and the deploy-time migration preserves coverage with a "needs review" surface for unconvertible entries.

**Independent Test**: In Subtab 2, add `nginx` `min_version=1.26` → a scan sees `1.24` non_compliant, `1.28` compliant; edit to `1.30` → `1.28` flips to non_compliant; each edit is audit-logged; migration collapses OpenSSH `7.*`/`9.*` to `min_version=9.0` and flags an invalid-only product for review.

### Tests for User Story 2

- [X] T012 [P] [US2] Threshold CRUD integration test in `tests/integration/test_reference_threshold_crud.py`: create/edit/delete threshold via API as operator AND admin, each emits a `CONFIG_CHANGE` audit row, invalid `min_version` rejected.
- [X] T013 [P] [US2] Migration integration test in `tests/integration/test_migration_0004.py`: seed pre-V0.7 enumerated rows, run upgrade, assert lowest-`valid` derivation, single collapsed row, and `needs_review=true` on an invalid-only product.

### Implementation for User Story 2

- [X] T014 [US2] Rework `src/asset_dashboard/reference_versions/service.py` for threshold CRUD (depends on T003): replace `version_match`/`status` handling with `min_version`/`model`/`note`; `validate_reference_version` requires `vendor`, `product`, and a comparator-parseable `min_version`; `update_entry` clears `needs_review`.
- [X] T015 [US2] Update `src/asset_dashboard/reference_versions/routes.py` to the threshold payload (`{vendor, product, model?, min_version, note?}`) and `_serialize` per contracts/http-api-delta.md §A (depends on T014); keep `require_operator` (operators + admins) and the existing `CONFIG_CHANGE` audit on every mutation.
- [X] T016 [US2] Update the version-dictionary block in `src/asset_dashboard/web/templates/configuration.html` (Subtab 2) to the threshold editor (vendor/product/model/min_version/note) and add a "needs review" list for migration-flagged entries.
- [X] T017 [US2] Add the Ukrainian i18n keys for the threshold editor + needs-review labels in `src/asset_dashboard/web/i18n.py` (all new strings via the `t()` catalog, FR-022).

**Checkpoint**: Thresholds are fully manageable in-app and the migration is verified.

---

## Phase 5: User Story 3 — Automated version ingestion from official sources (Priority: P3)

**Goal**: Admins configure tracked sources (vendor/URL/models); a standalone staging fetcher produces a signed bundle; the air-gapped app verifies integrity, shows a review diff, and applies thresholds on confirm — with zero runtime network access.

**Independent Test**: Run the staging fetcher for one vendor → signed bundle; in Subtab 2 add a source, upload the bundle → preview shows `9.0 → 9.9 (update)`; apply → threshold updated (`source=ingested`), audited; a tampered bundle is rejected with no change; operators get 403 on the ingestion endpoints; the app makes no outbound request.

### Tests for User Story 3

- [X] T018 [P] [US3] Bundle-integrity unit tests in `tests/unit/test_bundle_integrity.py` (FR-016a, contracts/bundle-format.md): valid HMAC/digest accepted; tampered payload, wrong `key_id`, missing field, unknown `schema` all rejected; key never appears in output.
- [X] T019 [P] [US3] Ingestion-import integration test in `tests/integration/test_ingestion_import.py`: preview/apply happy path (create + update), failed-entry skip (no write), downgrade/verdict-changing requires confirmation else `needs_review=true` (FR-018), one `CONFIG_CHANGE` import audit with provenance and no secret, admin-only (operator → 403) per FR-014.
- [X] T020 [P] [US3] Runtime-isolation test in `tests/integration/test_runtime_offline_imports.py` (FR-019): assert `src/asset_dashboard/` imports neither `tools.version_fetcher` nor an HTTP client (e.g. `httpx`/`requests`).

### Implementation for User Story 3

- [X] T021 [US3] Add pre-shared HMAC key loading (`key_id → key`) from local secure config in `src/asset_dashboard/config.py` (never logged/returned); used only for bundle verification.
- [X] T022 [US3] Implement bundle parse + canonicalization + SHA-256 + HMAC-SHA256 verification in `src/asset_dashboard/version_ingestion/bundle.py` per contracts/bundle-format.md (depends on T021); reject on any mismatch/unknown key/unparseable/unknown schema.
- [X] T023 [US3] Implement `src/asset_dashboard/version_ingestion/service.py` (depends on T022, T003, T004): tracked-source CRUD; import **preview** (verify → diff current vs incoming, compute `downgrade`/`verdict_changing` with `version_compare`); import **apply** (write `source="ingested"`, `source_ref`; skip `status!=ok` entries; gate downgrades behind confirmation else `needs_review=true`; update source `last_*`); emit `CONFIG_CHANGE` import audit per data-model.md §5.
- [X] T024 [US3] Implement `src/asset_dashboard/version_ingestion/routes.py` with `require_admin` on every endpoint per contracts/http-api-delta.md §B/§C: sources CRUD, `POST /api/version-ingestion/import/preview`, `POST /api/version-ingestion/import/apply` (depends on T023).
- [X] T025 [US3] Register the ingestion router in the app factory `src/asset_dashboard/main.py` (`app.include_router(...)` alongside the existing routers) (depends on T024).
- [X] T026 [P] [US3] Implement the fetcher core `tools/version_fetcher/fetch.py` per contracts/fetcher-cli.md: `fetch` one vendor + its models, per-model `ok`/`failed` (reason, `version:null`) with no fabrication (FR-017/FR-020).
- [X] T027 [P] [US3] Implement the pluggable extractor (CSS selector / regex + normalization) under `tools/version_fetcher/extractors/`, driven by the source's `extractor` config.
- [X] T028 [US3] Implement the bundle writer in `tools/version_fetcher/bundle_writer.py`: canonicalize `payload`, compute SHA-256 + HMAC-SHA256 with the provided key, write the JSON bundle (depends on T027).
- [X] T029 [US3] Add the ingestion-sources list + import/preview/apply panel to Configuration Subtab 2 in `src/asset_dashboard/web/templates/configuration.html` (admin-only view) (depends on T024).
- [X] T030 [US3] Add the Ukrainian i18n keys for ingestion sources + import review/apply in `src/asset_dashboard/web/i18n.py` (FR-022).

**Checkpoint**: Full fetch → bundle → verified import flow works; runtime stays offline.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T031 [P] Extend the i18n catalog contract test `tests/unit/test_i18n_help_coverage.py` to cover all new keys from T017/T030.
- [X] T032 [P] Document the offline update workflow (staging fetcher usage + bundle import + key provisioning) in the repo docs/README referenced by quickstart.md.
- [X] T033 Run the quickstart.md validation scenarios 1–5 end-to-end and confirm the Success-Criteria mapping holds.

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (P1)** → no deps.
- **Foundational (P2)** → after Setup; **blocks all user stories**. T005 depends on T003+T004; T006 on T003.
- **US1 (P3)** → after Foundational. MVP.
- **US2 (P4)** → after Foundational; independent of US1 (shares only the schema/migration).
- **US3 (P5)** → after Foundational; independent of US1/US2 (shares the comparator + threshold table).
- **Polish (P6)** → after the stories it touches (T031 after US2/US3 i18n; T033 after all).

### Within each story

- Tests first (write failing), then implementation: comparator/threshold → evaluate (US1); service → routes → template → i18n (US2); config/key → bundle → service → routes → router-registration → fetcher/extractor/writer → template → i18n (US3).

### Parallel opportunities

- T002 ∥ T001 (Setup).
- Foundational: T004 is independent of T003; T005/T006 wait on them.
- US1 tests T007 ∥ T008 ∥ T009.
- US2 tests T012 ∥ T013.
- US3 tests T018 ∥ T019 ∥ T020; staging-CLI tasks T026 ∥ T027 run parallel to the in-app T021–T025 (different tree, `tools/`).
- With capacity, US1/US2/US3 proceed in parallel once Foundational is done.

---

## Parallel Example: User Story 1

```bash
# Launch US1 tests together:
Task: "Comparator unit tests in tests/unit/test_version_compare.py"
Task: "Threshold-check unit tests in tests/unit/test_version_threshold_check.py"
Task: "Immutable-history integration test in tests/integration/test_immutable_history.py"
```

---

## Implementation Strategy

### MVP first (US1 only)

1. Phase 1 Setup → 2. Phase 2 Foundational → 3. Phase 3 US1 → **STOP & validate** (quickstart Scenario 1 + 4) → demo. Minimum-version compliance with immutable history is a complete, shippable increment on its own.

### Incremental delivery

Foundational → US1 (MVP) → US2 (manual threshold management + migration surfaced) → US3 (automated ingestion). Each adds value without breaking the previous.

### Parallel team strategy

After Foundational: Dev A → US1; Dev B → US2; Dev C → US3 (the `tools/version_fetcher/` CLI can be built fully in parallel since the app never imports it).

---

## Notes

- `[P]` = different files, no incomplete-task dependency.
- Air-gap invariant (FR-019): nothing under `src/asset_dashboard/` may import `tools/version_fetcher/` or an HTTP client — T020 guards this.
- Immutable history (FR-012a): verdicts are written once; never add a code path that recomputes historical findings.
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.

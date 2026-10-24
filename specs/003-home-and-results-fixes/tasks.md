---
description: "Task list for feature 003 — Home Page & Results Corrections"
---

# Tasks: Home Page & Results Corrections

**Input**: Design documents from `/specs/003-home-and-results-fixes/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/http-api-delta.md, quickstart.md

**Tests**: INCLUDED. The constitution (Principle V) mandates the CI invariant suite and SC-008 requires no regression; this is a correction/enhancement to a tested codebase, so each story carries contract/integration/unit tests.

**Organization**: Tasks are grouped by user story, in priority order (P1 → P4), each independently implementable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1–US6 per spec.md
- All paths are relative to the repository root; source under `src/asset_dashboard/`.

## Path Conventions

Single ASGI web app (features 001/002): source in `src/asset_dashboard/`, tests in `tests/{unit,integration,contract}/`, migrations in `migrations/versions/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the new module shells this feature adds.

- [X] T001 [P] Create package `src/asset_dashboard/reference_versions/` with an empty `__init__.py`
- [X] T002 [P] Create empty helper module `src/asset_dashboard/discovery/results_view.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared code used by more than one user story. MUST complete before US1/US6.

**⚠️ CRITICAL**: No user story work begins until this phase is complete.

- [X] T003 Add all new Ukrainian i18n keys for feature 003 in `src/asset_dashboard/web/i18n.py` — home heading/nav "Головна" (FR-001), recent-profiles & recent-scans labels, compliance "не застосовно", ports placeholder "Всі порти closed або filtered" (FR-010), remediation/expected-version labels, reference-versions view labels, and per-schedule target/label strings
- [X] T004 Add `target_override: list[str] | None = None` parameter to `start_run` in `src/asset_dashboard/discovery/runner.py`; when set, build `params_used["target_scope"]` from it instead of `profile.target_scope` and NEVER write it back to the profile row (shared by US1 target-less launch and US6 schedules; FR-003c/FR-021a)

**Checkpoint**: Shared strings and target injection ready — user stories can begin.

---

## Phase 3: User Story 1 - Useful Home page + target-less profiles (Priority: P1) 🎯 MVP

**Goal**: A non-empty "Головна" page listing the 5 most-recently-updated profiles (each Run-now) and the 20 most recent scans across ALL profiles; profiles may be saved without a target and launched by supplying the target at launch.

**Independent Test**: Sign in with a profile that has NO version evaluation and one completed scan; the Home page shows that scan and that profile with Run now; launching starts a run. Save a target-less profile; launch it from Home and the profiles list (each prompts for a target); confirm the target is used for that run only and not persisted.

### Tests for User Story 1

- [X] T005 [P] [US1] Contract test `POST /api/profiles/{id}/runs` with `target_scope` override and `400 target_required` when effective target empty, in `tests/contract/test_runs.py`
- [X] T006 [P] [US1] Contract test that `POST /api/profiles` and `PUT /api/profiles/{id}` accept an **empty** `target_scope` and still validate a present one, in `tests/contract/test_profiles.py`
- [X] T007 [P] [US1] Integration test Home page content — ≤5 recent profiles by most-recent, ≤20 recent scans across all profiles (including a scan from a non-compliance profile), heading/nav read "Головна", empty states — in `tests/integration/test_us1_home.py`
- [X] T008 [P] [US1] Integration test target-less launch from Home AND profiles list — prompt, run uses supplied target, profile stays target-less, invalid target rejected — in `tests/integration/test_us1_targetless_launch.py`
- [X] T009 [P] [US1] Unit test `validate_profile`/`validate_target_scope` allow empty target when `require_target=False` and still reject an invalid present target, in `tests/unit/test_validation_target_optional.py`

### Implementation for User Story 1

- [X] T010 [US1] Add a `require_target: bool = True` flag to `validate_target_scope` and `validate_profile` in `src/asset_dashboard/profiles/validation.py`; when `False`, an empty `target_scope` is valid, but a non-empty one is still fully validated (FR-003a)
- [X] T011 [US1] In `src/asset_dashboard/profiles/routes.py`, pass `require_target=False` in `api_create_profile`/`api_update_profile` so target-less profiles save (FR-003a) (depends on T010)
- [X] T012 [US1] In `src/asset_dashboard/discovery/routes.py`, add optional `target_scope: list[str] | None` to `StartRunRequest`; resolve effective target = override else profile target; empty → `400 target_required`; validate a provided override with `validate_target_scope`; when override provided skip the fresh-cache path; pass `target_override` into `start_run` (FR-003b/c/d) (depends on T004)
- [X] T013 [US1] Rework `src/asset_dashboard/web/dashboard.py` Home query: ≤5 `DiscoveryProfile` by `updated_at` desc regardless of `compliance_settings`, and ≤20 `DiscoveryRun` across ALL profiles by `started_at` desc with a findings posture when the run evaluated `version_validity` else compliance "not applicable" (FR-002/004/005/005a)
- [X] T014 [US1] Rewrite `src/asset_dashboard/web/templates/dashboard.html` as the Home page: recent-profiles section (each with a Run-now action that prompts for a target when the profile is target-less), recent-scans overview, empty-state messages, "Головна" heading (FR-001/002/003/005; empty-state edge cases) (depends on T013, T003)
- [X] T015 [US1] In `src/asset_dashboard/web/templates/profiles_list.html`, make the per-profile Run action prompt for a target when the profile is target-less so the profiles-list launch is never a dead end (clarification/FR-003b)

**Checkpoint**: US1 fully functional and independently testable — this is the MVP.

---

## Phase 4: User Story 6 - Schedule discovery-profile scans (Priority: P2)

**Goal**: Schedule a profile's scan to run recurringly as an independent task that carries its own target (target-less profiles schedulable; multiple schedules per profile), and create a schedule from a past scan.

**Independent Test**: Create a schedule referencing a profile, supplying the schedule's own target; let it fire (short interval or `tick()`); the scan runs against that target and is stored in history/audit like a manual run; create a second schedule for the same profile; from history, schedule a past scan reusing its profile+target.

### Tests for User Story 6

- [X] T016 [P] [US6] Contract tests for per-schedule CRUD (`GET/POST /api/profiles/{id}/schedules`, `PUT/DELETE /api/schedules/{id}`), per-schedule `target_scope` validation, and `POST /api/runs/{id}/schedule`, in `tests/contract/test_schedule.py`
- [X] T017 [P] [US6] Integration test: create schedule with own target, multiple schedules per profile, fire via `tick()`, create-from-history, empty/invalid target rejected, in `tests/integration/test_us6_schedule.py`
- [X] T018 [P] [US6] Unit test `tick()` passes `schedule.target_scope` as `target_override`, and schedule-target validation, in `tests/unit/test_schedule_target.py`

### Implementation for User Story 6

- [X] T019 [US6] Alembic migration `0003` in `migrations/versions/` — add `schedules.target_scope` (JSON, default `[]`) and `schedules.label` (`String(128)`, nullable), and DROP `UNIQUE(profile_id)` via an Alembic **batch** op (SQLite table rebuild)
- [X] T020 [US6] In `src/asset_dashboard/db/models.py` `Schedule`: add `target_scope` (JSON, default list) and `label` (`String(128)`, nullable); remove `unique=True` from `profile_id` (keep `ON DELETE CASCADE`) (pairs with T019)
- [X] T021 [US6] In `src/asset_dashboard/scheduling/engine.py` `tick()`, pass `target_override=schedule.target_scope` into `start_run` for due profile schedules (FR-021a/FR-022) (depends on T004, T020)
- [X] T022 [US6] Generalize `src/asset_dashboard/scheduling/routes.py` to per-schedule CRUD by `schedule_id` with `target_scope` (validated via `validate_target_scope`, non-empty required — FR-021b; defaults to the profile's saved target when omitted on create) and optional `label`; record `SCHEDULE_CHANGE` on each mutation (FR-020/021) (depends on T020)
- [X] T023 [US6] Add `POST /api/runs/{run_id}/schedule` (create-from-history) in `src/asset_dashboard/scheduling/routes.py`: copy the run's `profile_id` and `params_used.target_scope` onto a new schedule; `404` if the run's profile no longer exists (FR-023) (depends on T022)
- [X] T024 [US6] Update `src/asset_dashboard/web/templates/schedules.html` to show/edit per-schedule target + label and list multiple schedules per profile (FR-020/021) (depends on T022, T003)
- [X] T025 [US6] Add a "schedule this scan" action per run in `src/asset_dashboard/web/templates/history.html` calling `POST /api/runs/{id}/schedule` (FR-023) (depends on T023)

**Checkpoint**: US1 and US6 both work independently.

---

## Phase 5: User Story 2 - Dynamic UI without manual reload (Priority: P2)

**Goal**: Profile duplicate/delete/create/edit update the affected list in place via HTMX; a failed mutation stays consistent with server state and shows an error.

**Independent Test**: Duplicate a profile → copy appears with no reload; delete → row disappears with no reload; a failing mutation leaves the list consistent and shows an error.

### Tests for User Story 2

- [X] T026 [P] [US2] Integration test: duplicate appends a row and delete removes a row without a full reload, and a failed mutation leaves the list consistent with an error indication, in `tests/integration/test_us2_dynamic.py`

### Implementation for User Story 2

- [X] T027 [US2] In `src/asset_dashboard/profiles/routes.py`, when the request carries `HX-Request`, return an HTML `<tr>` fragment from the duplicate endpoint and a `200`/empty body from delete (keep JSON responses for API/tests) (FR-006/007)
- [X] T028 [US2] In `src/asset_dashboard/web/templates/profiles_list.html`, wire `hx-post` duplicate (append the returned row), `hx-delete` delete (remove the row), and an inline error region shown on a non-2xx response (FR-008) (depends on T027)

**Checkpoint**: US1, US6, US2 independently functional.

---

## Phase 6: User Story 3 - Port column adapts to scan size (Priority: P3)

**Goal**: Persist each port's state; small scan (≤10 ports in results) shows every port with its state, large scan (>10) shows open-only, large with no open ports shows "Всі порти closed або filtered"; version from an open port; a filtered/closed port is never shown as open.

**Independent Test**: Small scan on `1_prof_output.txt` → 192.168.1.1 shows `22/tcp open` and `8291/tcp filtered`; large scan → open-only; large with no open ports → placeholder text; shown version is from an open port.

### Tests for User Story 3

- [X] T029 [P] [US3] Unit test `_persist_assets` stores a `state` per port, sets `summary["ports_in_results"]` to the distinct `(port,protocol)` count, and selects `service_version` from an OPEN port only, in `tests/unit/test_runner_ports.py`
- [X] T030 [P] [US3] Unit test `results_view` model: `≤10` → small (all ports+state), `>10` → large (open-only), large with no open ports → `all_closed`, missing state treated as open, in `tests/unit/test_results_view.py`
- [X] T031 [P] [US3] Integration test ports column small vs large vs all-closed using `1_prof_output.txt`, in `tests/integration/test_us3_ports.py`

### Implementation for User Story 3

- [X] T032 [US3] In `src/asset_dashboard/discovery/runner.py` `_persist_assets`: add `"state": p.state` to each stored port dict, keep all responding-host ports, set `service_version = next((p.version for p in host.ports if p.state == "open" and p.version), None)`, and set `run.summary["ports_in_results"]` to the distinct `(port,protocol)` count (FR-009b/FR-011)
- [X] T033 [US3] Implement `src/asset_dashboard/discovery/results_view.py`: given a run's `ports_in_results` and an asset's ports, return `{mode, ports, all_closed}` — small lists every port with state, large filters to open, `all_closed` flags a large responding host with no open ports; treat a missing `state` as `open` (FR-009/009a/010) (depends on T002)
- [X] T034 [US3] Update `src/asset_dashboard/web/templates/run_detail.html` ports cell to use the `results_view` model: small shows `port/proto state`, large shows open-only, all-closed shows "Всі порти closed або filtered" (FR-009/009a/010) (depends on T033, T003)
- [X] T035 [US3] In `src/asset_dashboard/discovery/routes.py` `_serialize_results`/`_serialize_run`, include each port's `state` and the run's `ports_in_results` so the history detail view renders identically (FR-009)

**Checkpoint**: US1, US6, US2, US3 independently functional.

---

## Phase 7: User Story 4 - Non-compliant rows show expected version + reference view (Priority: P3)

**Goal**: Orange-highlight non-compliant rows, surface the expected valid version/note from the reference dataset, and provide an in-app reference-versions view editable by Operators and Administrators and audit-logged.

**Independent Test**: With OpenSSH 7.x invalid / 9.x valid, scan a host at 7.4 → row is orange, shows non_compliant and the expected valid version/note; compliant/unknown rows not orange; `/reference-versions` lists entries and both roles can edit, each edit audited.

### Tests for User Story 4

- [X] T036 [P] [US4] Unit test `check_version` attaches `expected_valid` from the matching `valid` entry for the same product on an invalid match, and attaches only the note (no invented version) when no valid entry exists, in `tests/unit/test_version_remediation.py`
- [X] T037 [P] [US4] Contract test reference-versions CRUD allowed for Operator and Administrator, validation of `status ∈ {valid,invalid}` and non-empty `vendor/product/version_match`, and `CONFIG_CHANGE` audit on each edit, in `tests/contract/test_reference_versions.py`
- [X] T038 [P] [US4] Integration test orange non-compliant row + expected-version cell + reference-versions view visible and editable, in `tests/integration/test_us4_remediation_reference.py`

### Implementation for User Story 4

- [X] T039 [US4] In `src/asset_dashboard/compliance/version_check.py`, on an `invalid` match look up the first `valid` `ReferenceVersionEntry` with the same `product` and add `expected_valid` (+ the invalid entry's `note`) to the returned detail; when no valid entry exists, carry only the note — never invent a version (FR-013; edge case)
- [X] T040 [US4] In `src/asset_dashboard/compliance/evaluate.py`, persist `expected_valid`/remediation into `ComplianceFinding.detail` for version findings (depends on T039)
- [X] T041 [US4] Implement `src/asset_dashboard/reference_versions/service.py`: list/create/update/delete `ReferenceVersionEntry` with validation (`status ∈ {valid,invalid}`, non-empty `vendor`/`product`/`version_match`) (depends on T001)
- [X] T042 [US4] Implement `src/asset_dashboard/reference_versions/routes.py`: `GET /reference-versions` page + JSON CRUD API (session auth, Operators AND Administrators, NOT admin-gated), recording `CONFIG_CHANGE` on each mutation (FR-015/015a/015b) (depends on T041)
- [X] T043 [US4] Register the reference-versions routers in `src/asset_dashboard/main.py` and add a nav link in `src/asset_dashboard/web/templates/base.html` (depends on T042, T003)
- [X] T044 [US4] Create `src/asset_dashboard/web/templates/reference_versions.html`: list (vendor, product, version_match, status, note) with inline add/edit/remove (FR-015/015a) (depends on T042)
- [X] T045 [US4] In `src/asset_dashboard/web/templates/run_detail.html`, add a `row-non-compliant` class when any finding `result == non_compliant` and render `expected_valid`/note in the compliance cell (FR-012/013/014) (depends on T034)
- [X] T046 [US4] In `src/asset_dashboard/web/static/base.css`, add the `.row-non-compliant` orange token from the existing dark SOC palette (FR-012)

**Checkpoint**: US1, US6, US2, US3, US4 independently functional.

---

## Phase 8: User Story 5 - NSE scripts selectable from a list control (Priority: P4)

**Goal**: Present allow-listed NSE scripts as a multi-select list/drop-down in the profile editor; persistence, allow-list validation, and command composition unchanged.

**Independent Test**: Open the profile editor → scripts offered as a list/drop-down; select, save, reopen → same scripts selected and in the command preview; a since-disabled script still fails save validation.

### Tests for User Story 5

- [X] T047 [P] [US5] Integration test NSE scripts offered via a list/drop-down, selection persists across save/reopen and appears in the command preview, and a stale (disabled) selection fails save, in `tests/integration/test_us5_nse_list.py`

### Implementation for User Story 5

- [X] T048 [US5] In `src/asset_dashboard/web/templates/profile_editor.html`, replace the NSE checklist with a `<select multiple>`/dropdown populated from the enabled allow-list (presentation only; persistence/validation/command composition unchanged) (FR-016/017)

**Checkpoint**: All user stories independently functional.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [X] T049 [P] Execute `specs/003-home-and-results-fixes/quickstart.md` end-to-end against a running app
- [X] T050 Run full `pytest`, `ruff check .`, `black --check .`; confirm all existing 001/002 tests still pass (SC-008)
- [X] T051 [P] Update `README.md`/help text where the Home page and nav label changed

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup; BLOCKS US1 and US6 (T004 is shared; T003 feeds all UI).
- **User Stories (Phases 3–8)**: depend on Foundational. US1 is the MVP. US6, US2, US3, US4, US5 are independently testable and may proceed in parallel after Phase 2 (subject to the within-story order below).
- **Polish (Phase 9)**: depends on the desired stories being complete.

### Cross-story notes

- **T004** (start_run `target_override`) is shared by US1 (T012) and US6 (T021) — it lives in Foundational so both stories stay independent.
- **T003** (i18n keys) is a single-file change feeding every UI task; done once in Foundational to avoid same-file conflicts.
- US4's T045 edits `run_detail.html` after US3's T034; if US3 is skipped, T045 still applies independently to the existing template.

### Within each user story

- Tests first (write failing), then models → services → routes → templates.
- US1: T010→T011; T012 needs T004; T013→T014.
- US6: T019↔T020 → T021/T022 → T023 → T024/T025.
- US3: T032 + T033 → T034/T035.
- US4: T039→T040; T041→T042→T043/T044; T045 needs T034.

### Parallel opportunities

- Setup: T001, T002 together.
- All `[P]` test tasks within a story run together (distinct files).
- Different user stories can be built in parallel by different developers after Phase 2.

---

## Parallel Example: User Story 1

```bash
# Tests together (distinct files):
Task: "Contract test runs target override in tests/contract/test_runs.py"       # T005
Task: "Contract test profile empty target in tests/contract/test_profiles.py"    # T006
Task: "Integration test Home page in tests/integration/test_us1_home.py"         # T007
Task: "Integration test target-less launch in tests/integration/test_us1_targetless_launch.py"  # T008
Task: "Unit test target-optional validation in tests/unit/test_validation_target_optional.py"   # T009
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → 2. Phase 2 Foundational → 3. Phase 3 US1 → **STOP and validate** the Home page and target-less launch independently → demo.

### Incremental Delivery

Setup + Foundational → US1 (MVP) → US6 → US2 → US3 → US4 → US5, validating each independently. US3 is the trust-restoring defect fix; US4 builds on its template but stands alone.

---

## Notes

- `[P]` = different files, no incomplete dependencies.
- No new runtime dependency (Principle I); device-safety/credential tool untouched (Principle III; FR-018).
- Launch-time and per-schedule targets reuse `validate_target_scope`; only the target is settable at launch (Principle II).
- Reference-version edits, schedule changes, and runs are audit-logged (Principle IV).
- Commit after each task or logical group; verify tests fail before implementing.

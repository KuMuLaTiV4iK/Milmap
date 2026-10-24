---
description: "Task list for feature 002 — Milmap discovery-profile enhancements"
---

# Tasks: Milmap — Discovery Profile Enhancements, NSE Scripts, Configuration, Roles & Ukrainian SOC UI

**Input**: Design documents from `/specs/002-discovery-profile-enhancements/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/http-api-delta.md](./contracts/http-api-delta.md)

**Tests**: INCLUDED — the project constitution (Principle V) mandates the CI invariant suite; tests are first-class here.

**Organization**: Tasks are grouped by user story (US1–US6) so each can be implemented and tested independently. This feature extends the existing `src/asset_dashboard/` codebase from feature 001.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US6 (Setup/Foundational/Polish carry no story label)

## Path Conventions

Single-project web app: source under `src/asset_dashboard/`, tests under `tests/`, migrations under `migrations/versions/`, reference seed data under `data/reference/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Scaffolding and package layout for the new modules.

- [X] T001 Create new package directories with `__init__.py`: `src/asset_dashboard/nse/`, `src/asset_dashboard/settings_store/`, `src/asset_dashboard/tools/`, `src/asset_dashboard/tools/credential_tool/`
- [X] T002 [P] Update `src/asset_dashboard/config.py`: set application name to "Milmap", add `default_locale = "uk"`, and add default values for `password_min_length` (20), `lockout_threshold`, `lockout_duration_seconds`, `session_idle_timeout_seconds` used as fallbacks by the settings store
- [X] T003 [P] Create NSE allow-list seed file `data/reference/nse_allowlist.json` with safe-category defaults including `{"script_id":"mikrotik-routeros-version","safety":"safe","expected_ports":[8291]}` and `{"script_id":"banner","safety":"safe"}` (data-model.md §Reference data)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema, models, roles, localization/theming scaffolding, and host-link removal that user stories build on.

**⚠️ CRITICAL**: No user story work begins until this phase is complete.

- [X] T004 Extend ORM in `src/asset_dashboard/db/models.py`: add `OperatorAccountRole` enum (`administrator`, `operator`) and a `role` column on `OperatorAccount` (default `operator`); add `selected_scripts` JSON column (default `[]`) to `DiscoveryProfile`; add `AuditEventType` members `ALLOWLIST_CHANGE`, `CONFIG_CHANGE`, `TOOL_CHECK`
- [X] T005 Add new ORM models in `src/asset_dashboard/db/models.py` per data-model.md: `NseScriptAllowlistEntry` (`script_id` unique, pattern `^[a-z0-9][a-z0-9._-]*$`, `safety` in {`safe`,`other`} default `safe`, `expected_ports` JSON, `enabled` bool, provenance), `SecuritySetting`, `ToolTask` (tool enum `default_credentials`, `target_scope`, `port`, `service`, `recurrence`, `overlap_policy`, `catch_up_policy`, `next_run_at`), `ToolCheckRun`, `ToolCheckResult` (`result` in {compliant,non_compliant,inconclusive}, `attempts_made` ≤ 3, `detail` never holds a secret)
- [X] T006 Create Alembic migration `migrations/versions/0002_feature_002.py`: add `role` + `selected_scripts` columns, create the five new tables, and add the new audit-enum values (depends on T004, T005)
- [X] T007 [P] Create `src/asset_dashboard/auth/authz.py`: `require_admin` and `require_operator` FastAPI dependencies that read the session user's role and return 403 `{"error":{"code":"forbidden"}}` for insufficient role
- [X] T008 [P] Create `src/asset_dashboard/web/i18n.py`: Ukrainian string catalog, help-text registry keyed by control id, and Jinja context helpers (`t(key)`, `help_for(control_id)`) plus a macro entry point for the `?` annotation (contract: every configuration control id must have a help entry)
- [X] T009 [P] Rework `src/asset_dashboard/web/static/base.css` into dark SOC color tokens (background, surfaces, text, accent) and distinct status colors (running/failed, compliant/non_compliant/inconclusive) — base tokens consumed by all templates
- [X] T010 Remove the host-management link capability (FR-004): in `src/asset_dashboard/profiles/validation.py` delete `validate_host_link_templates` and the `MIN_EXTRACTED_FIELDS` host-link path; in `src/asset_dashboard/profiles/routes.py` drop `host_links` from `ProfileIn`/`_serialize`/create/update; in `src/asset_dashboard/discovery/runner.py` stop populating `DiscoveredAsset.management_link`; in `src/asset_dashboard/web/templates/run_detail.html` stop rendering the management link (leave DB columns/table dormant)
- [X] T011 [P] Unit test host-link removal in `tests/unit/test_profile_validation.py`: a profile with no host link saves; no `{host}` validation runs; legacy `host_links` payload is ignored without error (depends on T010)

**Checkpoint**: Schema, roles, localization/theme scaffolding, and host-link removal ready — user stories can begin.

---

## Phase 3: User Story 1 - Edit an existing profile via a button (Priority: P1) 🎯 MVP

**Goal**: Operators edit a saved profile in place through an Edit button, with no duplicate created and optimistic-concurrency protection.

**Independent Test**: Open an existing profile via its Edit button, change fields, save → same profile updated, no duplicate; a stale `version_token` is rejected (409).

### Tests for User Story 1

- [X] T012 [P] [US1] Integration test `tests/integration/test_us1_edit.py`: `/profiles` list shows an Edit button per row; clicking loads the editor pre-filled; PUT updates in place (no new profile); stale `version_token` → 409
- [X] T013 [P] [US1] Contract test in `tests/contract/test_profiles.py`: `PUT /api/profiles/{id}` returns the updated profile (serializer has `selected_scripts`, no `host_links`) and 409 `stale_version` on token mismatch

### Implementation for User Story 1

- [X] T014 [US1] Add an **Edit** button to each row in `src/asset_dashboard/web/templates/profiles_list.html` linking to `/profiles/{id}` (alongside Run now / Duplicate / Delete)
- [X] T015 [US1] Verify/adjust the edit audit path in `src/asset_dashboard/profiles/routes.py` so an in-place update records a `PROFILE_CHANGE` with `action=update` (already present — confirm serializer no longer references host links)

**Checkpoint**: Profiles are editable via a button and update in place.

---

## Phase 4: User Story 2 - Full operator control over the scan command (Priority: P1)

**Goal**: Independent extraction toggles, `T3` default timing, an effective-command preview, and allow-list-only command composition.

**Independent Test**: Toggle each extraction option independently (incl. open-ports-only) and change timing; save/run; the preview matches selections exactly and `-sV` appears only when version extraction is on.

### Tests for User Story 2

- [X] T016 [P] [US2] Unit test `tests/unit/test_nmap_runner.py`: `build_nmap_command` includes `-T3` by default, includes `-sV` iff `service_version` is in `extracted_fields`, omits `-sV` for open-ports-only, and emits no raw/free-form flag
- [X] T017 [P] [US2] Unit test `tests/unit/test_profile_validation.py`: any subset of `{open_ports, service_version}` (including empty) is valid; the former minimum-fields rule is gone
- [X] T018 [P] [US2] Contract test `tests/contract/test_profiles.py`: `POST /api/profiles/preview-command` returns `{command: [...], display: "..."}` matching the payload and 422 on invalid payload
- [X] T019 [P] [US2] Integration test `tests/integration/test_us2_command_control.py`: new-profile timing defaults to `T3`; open-ports-only profile saves and runs with no version data and no error; preview matches selections

### Implementation for User Story 2

- [X] T020 [US2] In `src/asset_dashboard/discovery/nmap_runner.py`, make `build_nmap_command` honor `extracted_fields`: emit `-sV` when `service_version` is selected (collapse the old separate `service_detection` flag into this), default `timing` to `T3` when absent (depends on T010)
- [X] T021 [US2] In `src/asset_dashboard/profiles/routes.py`, pass through `extracted_fields` as sent (stop hardcoding), and add the `POST /api/profiles/preview-command` endpoint that returns `build_nmap_command(...)` output for an unsaved payload (reuses the runner's builder)
- [X] T022 [US2] Rework `src/asset_dashboard/web/templates/profile_editor.html`: make "Extract open ports" / "Extract service/firmware version" real enabled checkboxes (remove `disabled`), pre-select `T3` for new profiles, build `extracted_fields` from the checkboxes, map version extraction to `-sV` (drop the duplicate `service_detection` control), remove the host-link field/JS, remove the "Enable guarded default-credential compliance check" control and stop sending `default_credentials` in the saved `compliance_settings` (the credential check is standalone — US5; keep only the offline version-validity checkbox), and add a live effective-command preview panel calling `/api/profiles/preview-command`

**Checkpoint**: Operators fully control the composed command; US1 + US2 both work.

---

## Phase 5: User Story 3 - Configuration: account security, roles & user management (Priority: P1)

**Goal**: A Configuration area for self password change and (admin-only) user management, two roles, security settings with a ≥20 floor, and first-account-is-admin bootstrap.

**Independent Test**: Admin creates an Operator; the Operator can change their own password but not manage others (403); admin can't lower min length below 20 or remove the last admin; deactivation invalidates sessions.

### Tests for User Story 3

- [X] T023 [P] [US3] Contract test `tests/contract/test_users.py`: `GET/POST/PUT /api/users`, `POST /api/users/{id}/reset-password`; new users default to `operator`; removing/demoting the last admin → 409 `last_admin`
- [X] T024 [P] [US3] Contract test `tests/contract/test_settings.py`: `GET/PUT /api/settings/security`; `password_min_length` < 20 → 422; `POST /api/account/password` enforces the effective min length
- [X] T025 [P] [US3] Unit test `tests/unit/test_authz_and_settings.py`: `require_admin`/`require_operator` behavior; security-settings ≥20 floor clamp; last-active-admin guard
- [X] T026 [P] [US3] Integration test `tests/integration/test_us3_configuration.py`: full flow — admin creates operator, operator self-password only, 403 on admin APIs, settings floor, last-admin guard, deactivation invalidates session, all actions audited

### Implementation for User Story 3

- [X] T027 [P] [US3] Create `src/asset_dashboard/settings_store/service.py`: get/update effective security settings backed by `SecuritySetting`, falling back to `config.py`; reject `password_min_length` below the hard floor **20** (FR-032)
- [X] T028 [US3] Create `src/asset_dashboard/settings_store/routes.py`: `GET/PUT /api/settings/security` guarded by `require_admin`; audit `CONFIG_CHANGE` (depends on T027)
- [X] T029 [US3] Create `src/asset_dashboard/auth/routes_users.py`: admin user CRUD, role assignment, deactivate, reset-password; enforce the last-active-admin guard (409 `last_admin`); invalidate the target's session on deactivate/reset; audit `ACCOUNT_CHANGE` (depends on T007)
- [X] T030 [US3] Update `src/asset_dashboard/auth/routes.py`: add `POST /api/account/password` (self change, enforces effective min length) and expose `role` on the session user object
- [X] T031 [US3] Update auth to read effective settings from the store in `src/asset_dashboard/auth/passwords.py` (min length), `src/asset_dashboard/auth/sessions.py` (idle timeout), `src/asset_dashboard/auth/throttle.py` (lockout threshold/duration) (depends on T027)
- [X] T032 [US3] Update `src/asset_dashboard/auth/create_account.py`: assign the **first** account on a fresh install the `administrator` role; subsequent accounts default to `operator` (FR-030)
- [X] T033 [US3] Create `src/asset_dashboard/web/templates/configuration.html`: self password-change for all; admin-only sections for users and security settings (allow-list section added in US4); role-aware rendering
- [X] T034 [US3] Register the new routers in `src/asset_dashboard/main.py` and add a role-aware **Configuration** nav entry in `src/asset_dashboard/web/templates/base.html` (admin-only items hidden from operators)

**Checkpoint**: Roles, user management, security settings, and bootstrap work; P1 set (US1–US3) complete — minimum usable increment.

---

## Phase 6: User Story 4 - Select NSE scripts; manage the allow-list in Configuration (Priority: P2)

**Goal**: Profiles select NSE scripts from an admin-curated, UI-editable allow-list; selected scripts flow to `--script`; off-list scripts can't run.

**Independent Test**: Admin adds a script in Configuration → it appears in the profile checklist → a profile applying it runs with `--script`; removing it from the allow-list disables the selection.

### Tests for User Story 4

- [X] T035 [P] [US4] Contract test `tests/contract/test_nse.py`: `GET/POST/PUT/DELETE /api/nse-scripts` (admin for writes); non-safe add returns a non-blocking `warning`; `POST/PUT /api/profiles` with an off-list `selected_scripts` id → 422
- [X] T036 [P] [US4] Unit test `tests/unit/test_nse_allowlist.py`: `script_id` pattern/uniqueness validation; `build_nmap_command` adds `--script <ids>` for allow-listed ids only; selected-script validated against the allow-list; "port not in scope" warning when an entry's `expected_ports` are absent from the profile's port spec
- [X] T037 [P] [US4] Integration test `tests/integration/test_us4_nse.py`: add script → appears in checklist → profile runs with `--script` and captures per-host output; remove script → selection disabled/flagged

### Implementation for User Story 4

- [X] T038 [P] [US4] Create `src/asset_dashboard/nse/allowlist.py`: allow-list CRUD + validation (pattern, non-empty, no duplicates) and a default-seed loader from `data/reference/nse_allowlist.json`; wire the seed into `src/asset_dashboard/db/seed_reference.py`
- [X] T039 [US4] Create `src/asset_dashboard/nse/routes.py`: `GET /api/nse-scripts` (any authed) and admin `POST/PUT/DELETE` with the non-safe warning (FR-016) and `ALLOWLIST_CHANGE` audit; register router in `src/asset_dashboard/main.py` (depends on T038)
- [X] T040 [US4] In `src/asset_dashboard/profiles/validation.py`, validate `selected_scripts` against the current allow-list and add the expected-ports-not-in-scope warning (FR-013, FR-019)
- [X] T041 [US4] In `src/asset_dashboard/discovery/nmap_runner.py`, append a single `--script <comma-joined ids>` built from `selected_scripts` (allow-listed ids only) (depends on T020)
- [X] T042 [US4] In `src/asset_dashboard/profiles/routes.py`, accept `selected_scripts` in `ProfileIn`/`_serialize` and persist it; capture parsed NSE output per host under `DiscoveredAsset.extracted["nse"]` (a dict keyed by `script_id` → output text) via `src/asset_dashboard/discovery/parser.py`, so it persists in history with the rest of `extracted`
- [X] T043 [US4] Add the NSE checklist to `src/asset_dashboard/web/templates/profile_editor.html` (populated from `GET /api/nse-scripts`) and the allow-list editor section to `src/asset_dashboard/web/templates/configuration.html` (admin-only) (depends on T022, T033)

**Checkpoint**: NSE selection + allow-list management work (incl. the MikroTik example via the general capability).

---

## Phase 7: User Story 5 - Standalone default-credential tool (on demand or scheduled) (Priority: P2)

**Goal**: A separate credential-check tool (not profile automation) runnable on demand or on its own schedule via the shared scheduler, reusing the central 3-attempt/≥5 s guard.

**Independent Test**: Run on demand (attempts ≤ 3, ≥5 s apart, audited); schedule a task that fires and produces an equivalent run; a discovery profile run does NOT trigger the credential check.

### Tests for User Story 5

- [X] T044 [P] [US5] Contract test `tests/contract/test_credential_tool.py`: `POST /api/tools/credential-check`, `GET .../runs`, `GET .../runs/{id}`, and `GET/POST/PUT/DELETE .../tasks` (next_run_at shown; results never expose a secret)
- [X] T045 [P] [US5] Unit test `tests/unit/test_tool_scheduling.py`: `scheduling/engine.tick()` dispatches due `ToolTask`s, advances `next_run_at`, honors overlap/catch-up, and never exceeds the 3-attempt/≥5 s guard (reuse `check_default_credentials` with injected `sleep_fn`)
- [X] T046 [P] [US5] Integration test `tests/integration/test_us5_credential_tool.py`: on-demand run; scheduled run equivalent to on-demand; a discovery-profile run performs NO default-credential check

### Implementation for User Story 5

- [X] T047 [P] [US5] Create `src/asset_dashboard/tools/credential_tool/service.py`: on-demand run over `target_scope` reusing `compliance/credential_check.check_default_credentials`; persist `ToolCheckRun` + per-target `ToolCheckResult`; audit `TOOL_CHECK` (attempt counts/timings only, FR-024)
- [X] T048 [US5] Create `src/asset_dashboard/tools/credential_tool/tasks.py`: dispatch a `ToolTask` to the service (used by the scheduler) (depends on T047)
- [X] T049 [US5] Extend `src/asset_dashboard/scheduling/engine.py` `tick()` to also scan enabled due `ToolTask`s and dispatch via `tasks.py`, reusing `compute_next_run_at`, overlap and catch-up handling (FR-021); before dispatching, detect an in-progress `ToolCheckRun` (status `RUNNING`) for the same `ToolTask` and skip or defer per its `overlap_policy` so the same task never runs concurrently (depends on T048)
- [X] T050 [US5] Decouple from profile runs: remove the default-credential path from `src/asset_dashboard/compliance/evaluate.py` and `src/asset_dashboard/discovery/runner.py` so profile runs never trigger the credential check (FR-020) — the editor's default-credential control is removed in T022
- [X] T051 [US5] Create `src/asset_dashboard/tools/credential_tool/routes.py`: run-now, runs list/detail, and task CRUD endpoints + the `/tools/credential-check` page; register the router in `src/asset_dashboard/main.py` (depends on T047, T048)
- [X] T052 [US5] Create `src/asset_dashboard/web/templates/credential_tool.html`: on-demand run form, run history with per-target results, and schedule management
- [X] T053 [US5] Update `src/asset_dashboard/web/dashboard.py` so compliance posture reflects only profile `version_validity` plus (optionally) the standalone tool's latest results (no profile-run credential findings)

**Checkpoint**: Standalone credential tool works on demand and on schedule; profile runs are decoupled.

---

## Phase 8: User Story 6 - Dark SOC interface in Ukrainian with inline help (Priority: P2)

**Goal**: Consistent dark SOC theme, Ukrainian UI, Milmap branding, and a `?` help annotation on every configuration control; technical identifiers stay English.

**Independent Test**: Every screen renders dark + Ukrainian + Milmap; status indicators are legible; each config control shows a `?` help popup; `T3`/`-sV`/ports/script ids remain English.

### Tests for User Story 6

- [X] T054 [P] [US6] Unit test `tests/unit/test_i18n_help_coverage.py`: every configuration control id referenced by the templates has a Ukrainian help entry in `web/i18n.py` (FR-038)
- [X] T055 [P] [US6] Integration/smoke test `tests/integration/test_us6_ui_uk_dark.py`: login, profiles, editor, configuration, credential-tool, history, run-detail, schedules, dashboard each render with the dark theme, Ukrainian labels, Milmap brand, a `?` affordance on config controls, and literal English technical identifiers

### Implementation for User Story 6

- [X] T056 [US6] Finalize the dark SOC palette and status-color contrast in `src/asset_dashboard/web/static/base.css` (builds on T009)
- [X] T057 [US6] Update `src/asset_dashboard/web/templates/base.html`: Milmap branding, dark theme application, Ukrainian nav labels (role-aware)
- [X] T058 [US6] Populate the Ukrainian catalog and per-control help text in `src/asset_dashboard/web/i18n.py` for all configuration controls (timing `T3` → "Налаштування швидкості сканування", extraction options, security settings, allow-list fields, tool fields)
- [X] T059 [US6] Apply the i18n `t()`/`help_for()` helpers and the `?` help macro across all templates — `profiles_list.html`, `profile_editor.html`, `configuration.html`, `credential_tool.html`, `history.html`, `run_detail.html`, `schedules.html`, `login.html`, `dashboard.html` — keeping technical identifiers literal (depends on T008, T022, T033, T043, T052)

**Checkpoint**: All six user stories complete and independently verifiable.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Reconcile with feature 001, validate, and harden.

- [X] T060 Update feature-001 tests affected by decoupling in `tests/integration/test_us6_compliance.py` and any unit tests that assumed profile runs trigger the default-credential check (now standalone, US5)
- [X] T061 [P] Verify audit-log coverage across new events (`ALLOWLIST_CHANGE`, `CONFIG_CHANGE`, `TOOL_CHECK`, account/role changes) and assert no secrets in `detail` — extend `tests/unit/test_credential_guardrails.py`
- [X] T062 [P] Confirm air-gapped integrity: no new runtime dependency added (`pyproject.toml`/`requirements.lock` unchanged) and NSE runs from the local store only
- [X] T063 Run `alembic upgrade head`, `python -m asset_dashboard.db.seed_reference`, and the full `pytest` suite (unit + integration + contract); fix regressions — applied to the real dev `data/app.sqlite3` (backed up first); fixed a migration data-safety gap found along the way: the `role` column's `ADD COLUMN` default left every pre-existing account as `operator`, which would have locked the real admin out, so the migration now also promotes the earliest-created existing account to `administrator` on upgrade
- [X] T064 Execute the [quickstart.md](./quickstart.md) validation end-to-end (US1–US6) on a local instance — automated equivalent only: started the real ASGI app (not a browser) and confirmed the login page renders with Milmap branding + Ukrainian labels + the dark CSS; full user-story walkthroughs are covered by the integration test suite (`tests/integration/test_us1_edit.py` .. `test_us6_ui_uk_dark.py`), all passing. Manual browser + real-`nmap` validation against a live target was not performed in this environment and is still recommended before sign-off.

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup; **blocks all user stories**.
- **User Stories (Phases 3–8)**: all depend on Foundational.
- **Polish (Phase 9)**: depends on all targeted stories.

### User-story dependencies & shared-file notes

- **US1 (P1)**: independent after Foundational.
- **US2 (P1)**: independent after Foundational. Touches `nmap_runner.py`, `profiles/routes.py`, `profile_editor.html`.
- **US3 (P1)**: independent after Foundational (needs `authz.py` from T007).
- **US4 (P2)**: after Foundational; **shares files with US2** — T041 (`nmap_runner.py` `--script`) depends on T020; T043 edits `profile_editor.html` after T022 and `configuration.html` after T033. Run US4 after US2 and US3 to avoid conflicts.
- **US5 (P2)**: after Foundational; independent of US1–US4 except it edits `main.py` and `scheduling/engine.py`.
- **US6 (P2)**: after Foundational; **touches every template** — run last (depends on US2/US3/US4/US5 templates existing) so it localizes/themes the final markup.

### Within each story

- Tests first (write and see them fail) → models → services → endpoints → templates.

### Parallel opportunities

- Setup: T002, T003 in parallel.
- Foundational: T007, T008, T009 in parallel (distinct files); T004→T005→T006 are sequential (same model file / migration).
- All `[P]` test tasks within a story run together.
- Across stories: US1, US2, US3 can proceed in parallel after Foundational (distinct primary files, minding the shared `profile_editor.html` between US1's button and US2's rework — do T014 before or after T022, not concurrently).

---

## Implementation Strategy

### MVP scope

The **P1 trio (US1 + US2 + US3)** is the minimum usable increment: editable profiles, full command control with sane defaults, and the Configuration area with roles/users/security. Complete Phases 1–5, validate, then layer US4 (NSE), US5 (standalone credential tool), and US6 (dark Ukrainian UI) incrementally.

### Incremental delivery

1. Setup + Foundational → schema, roles, host-link removal ready.
2. US1 → US2 → US3 → validate the P1 increment (demo-able).
3. US4 → US5 → US6 → validate each independently.
4. Polish → reconcile 001 tests, run quickstart, full suite green.

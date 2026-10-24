---
description: "Task list for Scan-Result Host Pivot & Run Configuration Window"
---

# Tasks: Scan-Result Host Pivot & Run Configuration Window

**Input**: Design documents from `specs/009-results-pivot-scan-config/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/http-api-delta.md](./contracts/http-api-delta.md)

**Tests**: Included. The spec defines per-story Independent Tests and acceptance scenarios, the plan names concrete test files, and Constitution Principle V requires the CI invariant suite to stay green.

**Organization**: Tasks are grouped by user story (US1–US4) for independent implementation and testing. All paths are under the single project `src/asset_dashboard/` with tests under `tests/`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US4 for story-phase tasks; Setup/Foundational/Polish carry no story label

## ⚠️ Shared-file note

`src/asset_dashboard/web/templates/run_detail.html` is edited by Foundational, US2, US3, and US4. Edits to it are **sequential** (never marked `[P]` relative to each other), even across stories. `src/asset_dashboard/web/i18n.py` is append-only (new keys), so its edits are safely `[P]`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Shared visual affordances. No new dependencies (offline/air-gapped — Principle I).

- [X] T001 [P] Add selection-toolbar, row-checkbox-column, and disabled-action styles to `src/asset_dashboard/web/static/base.css` (used by the results-page selection toolbar and the Scan Configuration page)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The backend per-run-override seam (needed by US1 + US3) and the results-page selection mechanism (needed by US2 + US3 + US4). No user story can be completed until the pieces it depends on here are done.

**⚠️ CRITICAL**: US1 depends on T002–T004; US2/US3/US4 depend on T006.

### Backend: per-run overrides on the launch endpoint

- [X] T002 Extend `StartRunRequest` in `src/asset_dashboard/discovery/routes.py` with optional `port_spec: str | None = None`, `scan_params: dict | None = None`, and `extracted_fields: list[str] | None = None` (all default `None`, backward compatible)
- [X] T003 Extend `api_start_run` in `src/asset_dashboard/discovery/routes.py` to validate each present override via `profiles/validation.py` (`validate_port_spec`, `validate_scan_params` allow-list keys only, `validate_extracted_fields` subset of `{open_ports, service_version}`) returning `validation_error({field: msg})` on failure; and change the cache-serve guard so cache is served **only when no override is present** and `force_fresh` is false (today's `target_override is None` condition widened to "no override present")
- [X] T004 Extend `start_run(...)` in `src/asset_dashboard/discovery/runner.py` with `port_spec_override`, `scan_params_override`, `extracted_fields_override` params and apply them into `params_used` / `profile_snapshot` only when provided; the `DiscoveryProfile` row MUST NOT be written (one-off semantics, FR-017)
- [X] T005 [P] Contract test in `tests/contract/test_run_launch_overrides.py`: POST `/api/profiles/{id}/runs` accepts and applies `port_spec`/`scan_params`/`extracted_fields` overrides; rejects a disallowed `scan_params` key (e.g. `{"script":"x"}`) with `400`; the run's `params_used`/`profile_snapshot` reflect the overrides; the saved profile is **unchanged** (SC-004); any present override produces a fresh run (cache bypassed)

### Results page: selection mechanism

- [X] T006 Add per-row selection checkboxes, a header select-all / clear control, and a live selected-count indicator to `src/asset_dashboard/web/templates/run_detail.html`; pivot actions read the de-duplicated set of selected host addresses (FR-001, FR-002, FR-005)
- [X] T007 [P] Add i18n strings for the selection toolbar (selected-count label, "Select all", "Clear") to `src/asset_dashboard/web/i18n.py`

**Checkpoint**: Backend accepts one-off overrides (tested); results rows are selectable with a visible count. Story work can begin.

---

## Phase 3: User Story 1 - Review-driven Scan Configuration window (Priority: P1) 🎯 MVP

**Goal**: Replace the browser target prompt with a Scan Configuration page that opens on every **Run now**, pre-filled from the profile, with four editable one-off fields + command preview + **Start Scan**; saved profile never changes.

**Independent Test**: Click **Run now** on a targeted profile → config page opens pre-filled → Start Scan launches; on a target-less profile Start Scan is blocked until a target is entered; the saved profile is unchanged; no browser prompt appears anywhere.

**Depends on**: Foundational T002–T004 (override endpoint). Independent of the selection mechanism.

### Tests for User Story 1

- [X] T008 [P] [US1] Integration test in `tests/integration/test_scan_config_page.py`: `GET /profiles/{id}/scan` renders pre-filled fields; a target-less profile cannot launch with an empty target (server returns `target_required`); launching with edited timing/ports starts a run whose params reflect the edits while the saved profile is unchanged; `dashboard.html` and `profiles_list.html` no longer contain a `window.prompt` call (SC-005)

### Implementation for User Story 1

- [X] T009 [US1] Add page route `GET /profiles/{profile_id}/scan` in `src/asset_dashboard/profiles/routes.py` rendering `scan_config.html`, pre-filled from the profile, honoring an optional `?targets=` comma-separated query param that overrides the target field for display; `404` when the profile is missing
- [X] T010 [US1] Create `src/asset_dashboard/web/templates/scan_config.html`: four editable fields — target scope, port spec, timing (T0–T5), extracted fields (`open_ports`, `service_version`); a **read-only** reflection of the version-validity compliance toggle and NSE selection (FR-014); live command preview via `POST /api/profiles/preview-command`; a **Start Scan** button that POSTs to `/api/profiles/{id}/runs` sending **only the fields changed from the profile** (unchanged targeted runs send an empty body → cache eligible, per research R2), is disabled until the target is non-empty (FR-016), and on success redirects to `/runs/{run_id}`
- [X] T011 [P] [US1] Replace `startRun()` + `window.prompt(...)` in `src/asset_dashboard/web/templates/dashboard.html` with navigation to `/profiles/{id}/scan` for the **Run now** button
- [X] T012 [P] [US1] Replace the `window.prompt(...)` launch path in `src/asset_dashboard/web/templates/profiles_list.html` with navigation to `/profiles/{id}/scan`
- [X] T013 [P] [US1] Add i18n strings for the Scan Configuration page (page title, "Start Scan", target-required hint, read-only compliance/NSE labels) to `src/asset_dashboard/web/i18n.py`

**Checkpoint**: Run now opens a real configuration page; the prompt is gone (SC-005); one-off launches never mutate the profile (SC-004). MVP is demoable.

---

## Phase 4: User Story 2 - Select hosts and run a credential check (Priority: P1)

**Goal**: From the results table, tick hosts and **Check credentials on selected** → the credential tool opens pre-filled with those addresses; the check runs under the unchanged central guard.

**Independent Test**: Select 2+ hosts → **Check credentials on selected** → `/tools/credential-check?targets=…` opens with exactly those addresses pre-filled; the action is disabled with 0 selected.

**Depends on**: Foundational T006 (selection mechanism).

### Tests for User Story 2

- [X] T014 [P] [US2] Integration test in `tests/integration/test_cred_pivot.py`: the credential-tool page pre-fills `run_target_scope` from `?targets=10.0.0.5,10.0.0.8`; and (server-side) a launched check from those targets runs under the ≥5s cooldown / attempt ceiling and is recorded in the audit log (SC-002, SC-006, FR-007/009)

### Implementation for User Story 2

- [X] T015 [US2] Add a **Check credentials on selected** action to the selection toolbar in `src/asset_dashboard/web/templates/run_detail.html` that builds the de-duplicated selected-address list and navigates to `/tools/credential-check?targets=<csv>`; disabled when 0 hosts are selected (FR-006, FR-002)
- [X] T016 [US2] Pre-fill the Run-now target field from the `?targets=` query param on load in `src/asset_dashboard/web/templates/credential_tool.html` (operator still chooses port/service/dictionary — FR-008)
- [X] T017 [P] [US2] Add i18n string "Check credentials on selected" to `src/asset_dashboard/web/i18n.py`

**Checkpoint**: Credential-check pivot works end-to-end; guardrails and audit intact; US1 still works.

---

## Phase 5: User Story 3 - Select hosts and run another scan against them (Priority: P1)

**Goal**: From the results table, tick hosts and **Scan selected with profile…** → pick a profile → the Scan Configuration page (US1) opens pre-filled with those hosts as the target; Start Scan runs exactly those hosts without changing the profile.

**Independent Test**: Select hosts → **Scan selected with profile…** → pick a profile → `/profiles/{id}/scan?targets=…` opens pre-filled; Start Scan launches a run targeting exactly those hosts; the chosen profile's saved target is unchanged; relaunching the same profile while running surfaces a `409` message.

**Depends on**: Foundational T006 (selection) **and** US1 T009/T010 (the Scan Configuration page + its `?targets=` handling).

### Tests for User Story 3

- [X] T018 [P] [US3] Integration test in `tests/integration/test_scan_pivot.py`: navigating to `/profiles/{id}/scan?targets=…` pre-fills exactly those hosts; Start Scan creates a run whose effective target equals the shown hosts while the profile is unchanged (SC-001, SC-004); a second launch of an already-running profile returns `409 already_running` (FR-019)

### Implementation for User Story 3

- [X] T019 [US3] Add a **Scan selected with profile…** control to the selection toolbar in `src/asset_dashboard/web/templates/run_detail.html`: a profile picker populated from `GET /api/profiles`; on selection, navigate to `/profiles/{id}/scan?targets=<csv of selected>`; disabled when 0 hosts are selected (FR-010, FR-011)
- [X] T020 [P] [US3] Add i18n strings for "Scan selected with profile…" and the profile-picker placeholder to `src/asset_dashboard/web/i18n.py`

**Checkpoint**: Both pivots (credential + scan) and Run now all work; each is independently testable.

---

## Phase 6: User Story 4 - Auto-select hosts with an invalid version (Priority: P2)

**Goal**: One click selects every host whose version-validity result is `non_compliant` (excluding `unknown` and `compliant`), **added to** the current selection (union); disabled when the run was not version-evaluated.

**Independent Test**: On a version-evaluated run with mixed results, tick one compliant host then click **Select invalid-version hosts** → all `non_compliant` rows become selected in addition to the manual tick; no `unknown`/`compliant` row is auto-selected; on a non-version-evaluated run the action is disabled.

**Depends on**: Foundational T006 (selection mechanism).

### Tests for User Story 4

- [X] T021 [P] [US4] Integration test in `tests/integration/test_invalid_version_select.py`: `run_detail` renders each host row annotated with its version-validity result (`non_compliant` / `unknown` / `compliant`), and the **Select invalid-version hosts** control is present-and-enabled for a version-evaluated run but disabled for a run without version-validity findings (FR-003, FR-004, SC-003)

### Implementation for User Story 4

- [X] T022 [US4] Annotate each results row with its version-validity result (e.g. `data-version-result="non_compliant|unknown|compliant"`) and render a **Select invalid-version hosts** toolbar button in `src/asset_dashboard/web/templates/run_detail.html`, disabled when the run has no version-validity evaluation (FR-004)
- [X] T023 [US4] Implement the auto-select behavior in `src/asset_dashboard/web/templates/run_detail.html`: clicking the button ticks every row with `data-version-result="non_compliant"`, **adds** them to the current selection without un-ticking anything (union, FR-003), and updates the selected-count
- [X] T024 [P] [US4] Add i18n strings for "Select invalid-version hosts" and the "not evaluated for version" disabled hint to `src/asset_dashboard/web/i18n.py`

**Checkpoint**: All four stories independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T025 [P] Retire the now-unused `dashboard.target_required_prompt` i18n key (or mark it deprecated) in `src/asset_dashboard/web/i18n.py` once no template references it
- [X] T026 Run the full suite `pytest tests/` and confirm the existing CI invariants (auth gate, allow-list validation, duplicate-run prevention) stay green (Principle V)
- [X] T027 Execute the [quickstart.md](./quickstart.md) validation scenarios A–D manually and confirm SC-001…SC-007
- [X] T028 [P] Final pass on `run_detail.html` toolbar: keyboard focus order and disabled-state affordances for the selection actions (accessibility of the new controls)

---

## Phase 8: Post-review course corrections (user feedback 2026-10-24)

Direct user corrections after the first demo; these override the earlier
read-only-field and profile-linked-only decisions.

- [X] T029 Results table renders **one port per line** (`<ul class="port-list">`) in `run_detail.html` + supporting CSS
- [X] T030 The Scan window (`scan_config.html`) is the **full editable** config (target, ports, timing, extracted fields, compliance toggle, NSE scripts) titled "Сканування", with **Start Scan** + **Зберегти як профіль**; NSE now a **checkbox list** (decision: fully editable)
- [X] T031 Backend: extend `POST /api/profiles/{id}/runs` overrides with `selected_scripts` + `compliance_settings` (allow-list validated) so a profile-linked scan stays linked/cache-aware while fully editable (`discovery/routes.py`, `discovery/runner.py`)
- [X] T032 Backend: new **ad-hoc run** path — `start_adhoc_run()` + `POST /api/runs/ad-hoc` — runs a one-off scan WITHOUT persisting a profile (`profile_id` null, full config snapshotted/audited); shared `_launch()` core (decision: run without saving)
- [X] T033 New `GET /scan` **custom-scan** page (blank config) + "Довільне сканування" button above the recent-profiles table on the dashboard
- [X] T034 Profile editor (`profile_editor.html`): NSE as a **checkbox list**; added an immediate **Почати сканування** (ad-hoc) button so you can scan straight from the new-profile tab
- [X] T035 Tests: `tests/contract/test_adhoc_run.py` (ad-hoc endpoint + custom-scan page); updated `tests/integration/test_us5_nse_list.py` for the checkbox control; extended `test_run_launch_overrides.py` coverage

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: after Setup. T002→T003→T004 are sequential (same endpoint/path); T005 [P] after T004. T006 then T007 [P].
- **US1 (Phase 3)**: needs T002–T004. Independent of selection — can run in parallel with the selection infra once the override endpoint is done.
- **US2 (Phase 4)**: needs T006.
- **US3 (Phase 5)**: needs T006 **and** US1 (T009/T010).
- **US4 (Phase 6)**: needs T006.
- **Polish (Phase 7)**: after the desired stories are complete.

### User-story dependency notes

- US1 and US2 are independent of each other (different surfaces) and can proceed in parallel after Foundational.
- US3 reuses US1's Scan Configuration page, so US1 lands first (or together).
- US4 is independent of US2/US3 but shares `run_detail.html` with them (serialize the edits).

### Shared-file serialization (`run_detail.html`)

T006 (foundational) → then T015 (US2) / T019 (US3) / T022+T023 (US4) each edit the same file. Do them one at a time; none are `[P]` with each other.

---

## Parallel Opportunities

- **Setup**: T001.
- **Foundational**: T005 [P] (test file) alongside T007 [P] (i18n); the route/runner edits (T002–T004, T006) are sequential by file.
- **US1**: T008 [P] (test) up front; T011 / T012 / T013 all [P] (distinct files) after T009/T010.
- **US2**: T014 [P] (test) and T017 [P] (i18n) alongside the sequential T015/T016.
- **US3**: T018 [P] (test) and T020 [P] (i18n).
- **US4**: T021 [P] (test) and T024 [P] (i18n); T022→T023 sequential (same file).
- Across stories: the i18n additions (T007, T013, T017, T020, T024) are append-only and all [P]; the integration/contract/unit test files are distinct and all [P].

### Parallel example (after Foundational)

```bash
# Developer A drives US1 (no selection dependency):
Task: "T009 Add GET /profiles/{id}/scan route"
Task: "T010 Create scan_config.html"
# Developer B drives US2 (needs T006 only):
Task: "T015 Add 'Check credentials on selected' toolbar action"
Task: "T016 Pre-fill credential_tool.html from ?targets="
```

---

## Implementation Strategy

### MVP first (US1)

1. Phase 1 Setup → 2. Foundational T002–T005 (override endpoint) → 3. US1 → **validate**: Run now opens the config page, prompt gone, profile unchanged. Demo.

### Incremental delivery

1. Setup + Foundational (override endpoint + selection infra).
2. US1 (Scan Configuration page) → test → demo (MVP).
3. US2 (credential pivot) → test → demo.
4. US3 (scan pivot) → test → demo.
5. US4 (auto-select) → test → demo.
6. Polish.

Each story adds value without breaking the previous ones; stop at any checkpoint to validate independently.

---

## Notes

- `[P]` = different files, no dependency on an incomplete task.
- No database migration and no new dependency (Principle I, VI) — this is a UI feature over a small backward-compatible endpoint extension.
- The credential pivot introduces **no** new attempt path: it only pre-fills the existing credential-tool form, so the central guard (≥5s cooldown, configurable ceiling, stop-on-match) and audit logging are inherited unchanged (Principle III/IV).
- Per-run overrides are validated by the existing allow-list validators — no raw nmap flag can be injected (FR-018).
- Commit after each task or logical group.

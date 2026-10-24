---
description: "Task list for feature 006 — UI Layout Refinements"
---

# Tasks: UI Layout Refinements

**Input**: Design documents from `specs/006-ui-layout-refinements/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ui-contract.md, quickstart.md

**Tests**: Included. The project's constitution (Principle V) requires each slice to be covered and keeps a CI invariant suite green (incl. role-based access control and the i18n help-coverage contract), so test tasks are part of every story.

**Organization**: Grouped by user story (US1–US5 from spec.md) for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US5 (setup/foundational/polish carry no story label)
- All paths are repo-relative from `D:\MITIT\Milmap`.

## Path Conventions

Single project, server-rendered web app. Touched areas:
`src/asset_dashboard/web/templates/`, `src/asset_dashboard/web/dashboard.py`, `src/asset_dashboard/web/i18n.py`, `src/asset_dashboard/static/base.css`, `src/asset_dashboard/profiles/routes.py`, `src/asset_dashboard/reference_versions/routes.py`, and `tests/`.

---

## Phase 1: Setup (Shared)

**Purpose**: Establish a known-good baseline before editing.

- [X] T001 Confirm feature branch `006-ui-layout-refinements` is active and run the baseline suite `python -m pytest -q` to record current green state (no code change).
- [X] T002 [P] Locate `src/asset_dashboard/static/base.css` and skim its existing card/table/badge classes so new rules (`.home-columns`, textarea, subtabs) reuse existing tokens rather than inventing colors.

**Checkpoint**: Baseline green; CSS conventions known.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The responsive Home two-column shell that both Home stories (US1, US2) render into.

**⚠️ CRITICAL**: US1 and US2 both place content inside this layout; complete before those stories.

- [X] T003 Add a responsive two-column layout utility to `src/asset_dashboard/static/base.css`: a `.home-columns` container (flex or CSS grid, gap) with `.home-col-left` / `.home-col-right` children; stack to a single column below ~900px via a media query; ensure no horizontal page scroll at ~375px (SC-008). Use existing color/spacing tokens only (offline; no external assets).

**Checkpoint**: Layout utility available for the Home page.

---

## Phase 3: User Story 1 — Faster Home-page overview (Priority: P1) 🎯 MVP

**Goal**: Declutter Home: remove the heading/subtitle, split profiles (left) vs recent scans (right), and drop the three compliance columns while keeping "Не відповідає".

**Independent Test**: Load `/` with ≥1 profile and several scans; confirm heading/subtitle gone, two-column split present, and only the allowed scan columns render; stack with no horizontal scroll at narrow width.

### Tests for User Story 1 ⚠️ (write first, expect fail)

- [X] T004 [P] [US1] Add/extend a rendered-HTML test for `GET /` in `tests/integration/test_dashboard_page.py` (create if absent) asserting: the `dashboard.subtitle` text is absent; no `dashboard.col_compliant`/`col_unknown`/`col_inconclusive` header text; `dashboard.col_non_compliant` ("Не відповідає") still present; a `.home-columns` element exists with profiles in the left column and scans in the right.

### Implementation for User Story 1

- [X] T005 [US1] In `src/asset_dashboard/web/templates/dashboard.html`, remove the `<h1>{{ t('dashboard.title') }}</h1>` and `<p>{{ t('dashboard.subtitle') }}</p>` lines (FR-001).
- [X] T006 [US1] In `src/asset_dashboard/web/templates/dashboard.html`, wrap content in `.home-columns`: left column = recent-profiles card (and the US2 schedules card slot), right column = recent-scans card (FR-002). Keep the footer links row below the columns.
- [X] T007 [US1] In `src/asset_dashboard/web/templates/dashboard.html` recent-scans table, remove the three `<th>` for `dashboard.col_compliant`, `dashboard.col_unknown`, `dashboard.col_inconclusive`, and the matching `<td>` badges; keep `dashboard.col_non_compliant`. Update the `{% if scan.evaluated %}` fallback `colspan` from 4 → 1 and the empty-row `colspan` from 7 → 4 (FR-005, A-002).
- [X] T008 [P] [US1] In `src/asset_dashboard/web/i18n.py`, remove the now-unused `dashboard.col_compliant`, `dashboard.col_unknown`, `dashboard.col_inconclusive` keys ONLY after confirming (grep) no other template/test references them; leave `dashboard.title`/`dashboard.subtitle` in the catalog (unused on Home is fine). Do not break `tests/unit/test_i18n_help_coverage.py` (FR-017).

**Checkpoint**: Home is decluttered and two-column; US1 independently testable.

---

## Phase 4: User Story 2 — Reach scheduled tasks from Home (Priority: P2)

**Goal**: Show up to 5 soonest-upcoming enabled schedules under the profiles list; each links to `/schedules`.

**Independent Test**: With ≥1 enabled schedule, `/` shows ≤5 schedule rows (soonest `next_run_at` first) under the profiles card; clicking one navigates to `/schedules`; empty state renders with no error.

**Dependency**: Requires the Home left column from US1/Foundational (T003, T006).

### Tests for User Story 2 ⚠️

- [X] T009 [P] [US2] Add a view test in `tests/integration/test_dashboard_page.py` (or a unit test for the read-model) asserting `GET /` context `upcoming_schedules` contains only enabled schedules, ordered by `next_run_at` ascending, limit 5; and that a disabled schedule is excluded and an empty set yields the empty state (FR-003, FR-006).

### Implementation for User Story 2

- [X] T010 [US2] In `src/asset_dashboard/web/dashboard.py`, add an `upcoming_schedules` read-model: query `Schedule` where `enabled == True`, `order_by(Schedule.next_run_at.asc())`, `.limit(5)`; for each, resolve profile name via `profile_id` (fallback `"(deleted)"` like `schedules_page`), and build `{ id, profile_name, label, next_run_at }`. Pass it in the `TemplateResponse` context. Import `Schedule` from `asset_dashboard.db.models` (FR-003, RM-3).
- [X] T011 [US2] In `src/asset_dashboard/web/templates/dashboard.html`, add an "upcoming schedules" card in the left column beneath the profiles card: list each row as a link to `/schedules` showing `label or profile_name` + `next_run_at`; keyboard-activatable; render an empty-state message when the list is empty (FR-003, FR-004, FR-006).
- [X] T012 [P] [US2] In `src/asset_dashboard/web/i18n.py`, add keys for the schedules section title and empty state (e.g. `dashboard.upcoming_schedules_title`, `dashboard.upcoming_schedules_none`) in Ukrainian; reference them from the template (FR-017).

**Checkpoint**: Home surfaces upcoming schedules linking to the Schedules page.

---

## Phase 5: User Story 3 — Clearer profile editing (Priority: P2)

**Goal**: Command preview renders with no target (placeholder), and the ports field shows its full contents.

**Independent Test**: Open `/profiles/new` (no target) → preview shows a full `nmap` command with a visible placeholder; type a target → placeholder replaced; paste 20+ ports → all visible, saves and validates.

### Tests for User Story 3 ⚠️

- [X] T013 [P] [US3] Add an API test in `tests/integration/test_profiles_api.py` (or existing profiles test module) for `POST /api/profiles/preview-command`: with `target_scope: []` returns `200` and `display` contains the placeholder token; with a valid non-empty target returns the executable command; with an invalid `port_spec` still returns a validation error (C-API-1, FR-008/FR-009).

### Implementation for User Story 3

- [X] T014 [US3] In `src/asset_dashboard/profiles/routes.py` `api_preview_command`, pass `require_target=False` to `validate_profile(...)`; when `body.target_scope` is empty, call `build_nmap_command` with a single placeholder target token (e.g. `"<ціль>"`) so `display` is a complete, clearly-marked command; keep the real-target path unchanged so preview/execution parity holds (FR-008, FR-009, C-API-1).
- [X] T015 [US3] In `src/asset_dashboard/web/templates/profile_editor.html`, replace the single-line `<input id="port_spec">` (line ~30) with a full-width, vertically resizable `<textarea id="port_spec">` (small default rows, `resize: vertical`, wraps), preserving the `placeholder` and the preview-trigger event listeners on `port_spec` (FR-010).
- [X] T016 [US3] In `src/asset_dashboard/web/templates/profile_editor.html` `readForm()`, strip whitespace/newlines from the ports value before sending (e.g. `.value.replace(/\s+/g,'')`) so the server-side `_PORT_SPEC_RE` (no spaces) still validates a multi-line textarea entry (FR-010, SC-004).
- [X] T017 [P] [US3] If needed, add a small `textarea#port_spec` style rule in `src/asset_dashboard/static/base.css` (full width, min-height, vertical resize) using existing form tokens.

**Checkpoint**: Editor previews without a target and shows full port lists.

---

## Phase 6: User Story 4 — Simpler Profiles & History tables (Priority: P3)

**Goal**: Remove the "Розклад" column from Profiles and the "З кешу?" column from History.

**Independent Test**: `/profiles` has no "Розклад" header/cells; `/history` has no "З кешу?" header/cells; other columns intact.

### Tests for User Story 4 ⚠️

- [X] T018 [P] [US4] Add/extend rendered-HTML tests asserting `GET /profiles` has no `profiles.col_schedule` ("Розклад") header and `GET /history` has no `history.col_cached` ("З кешу?") header, with remaining headers present, in `tests/integration/test_profiles_page.py` and `tests/integration/test_history_page.py` (create if absent) (FR-007, FR-011).

### Implementation for User Story 4

- [X] T019 [P] [US4] In `src/asset_dashboard/web/templates/_macros.html` `profile_row`, remove the schedule `<td>` (`{{ t('profiles.scheduled') ... }}`); and in `src/asset_dashboard/web/templates/profiles_list.html` remove the `profiles.col_schedule` `<th>` and change the empty-row `colspan` 5 → 4 (FR-007, RM-4).
- [X] T020 [P] [US4] In `src/asset_dashboard/web/templates/history.html`, remove the `history.col_cached` `<th>` and the per-row cache `<td>` (`served_from_cache` → yes/no); change the empty-row `colspan` 6 → 5 (FR-011, RM-5).
- [X] T021 [US4] In `src/asset_dashboard/web/i18n.py`, remove `profiles.col_schedule` and `history.col_cached` (and `profiles.scheduled`, `history.yes`/`history.no` if now unreferenced — grep first; they may be used elsewhere) without breaking the i18n coverage test (FR-017).

**Checkpoint**: Both tables simplified.

---

## Phase 7: User Story 5 — Role-aware Configuration subtabs (Priority: P2)

**Goal**: Admin Configuration splits into Subtab 1 (Users + Security/session) and Subtab 2 (NSE allow-list + Version dictionary); operators see only own-credentials + version dictionary; standalone version-dictionary nav removed and old page redirected; server-side role gating unchanged.

**Independent Test**: As admin, two subtabs with the right grouping and no reload on switch; as operator, only own-password + version-dictionary cards; nav lacks "Довідник версій"; `/reference-versions` redirects to `/configuration`; operator admin-API calls still 403.

### Tests for User Story 5 ⚠️

- [X] T022 [P] [US5] Add role-rendering tests in `tests/integration/test_configuration_page.py` (create if absent): admin `/configuration` DOM contains users + security + NSE + reference-versions sections grouped into two subtabs; operator `/configuration` DOM contains only own-password + reference-versions sections and NOT users/security/NSE (FR-012, FR-014).
- [X] T023 [P] [US5] Add a test asserting `GET /reference-versions` redirects to `/configuration` and that `base.html` nav no longer links `nav.reference_versions` (FR-013a, C-API-2, C-CFG-4).
- [X] T024 [P] [US5] Add/confirm a role-enforcement test: as operator, `GET /api/users`, `PUT /api/settings/security`, `POST /api/nse-scripts` return 403, while `GET/POST /api/reference-versions` succeed (FR-015, SC-007) in `tests/integration/test_authz.py` (or the existing authz test module).

### Implementation for User Story 5

- [X] T025 [US5] Extract the version-dictionary (reference-versions) table + add/edit/delete form and its JS from `src/asset_dashboard/web/templates/reference_versions.html` into a reusable include/partial (e.g. `src/asset_dashboard/web/templates/_reference_versions.html`), parameterized so it works embedded in Configuration (FR-013).
- [X] T026 [US5] Rework `src/asset_dashboard/web/templates/configuration.html`: for `session_role == 'administrator'`, wrap content in an in-page two-subtab control — Subtab 1 = Users card + Security settings card; Subtab 2 = NSE allow-list card + the version-dictionary partial. Keep the existing `{% if session_role == 'administrator' %}` gate around admin-only cards (FR-012, FR-013).
- [X] T027 [US5] In `src/asset_dashboard/web/templates/configuration.html`, for operators (non-admin) render a flat view: own-password card + the version-dictionary partial only (no subtab chrome, no admin cards) (FR-014).
- [X] T028 [US5] Add the subtab toggle: a small inline JS show/hide between two `<section>`s (pure view toggle, no navigation/reload, no persisted state) plus minimal CSS for the tab buttons in `src/asset_dashboard/static/base.css`; ensure switching preserves entered form values (FR-016, C-CFG-2).
- [X] T029 [US5] Ensure the embedded version-dictionary JS loads its data (`GET /api/reference-versions`) on the Configuration page for both roles; reconcile any element-id collisions introduced by embedding (FR-013, FR-014).
- [X] T030 [US5] In `src/asset_dashboard/web/templates/base.html`, remove the `nav.reference_versions` link (and its surrounding `·` separator) from the nav (FR-013a).
- [X] T031 [US5] In `src/asset_dashboard/reference_versions/routes.py`, change `reference_versions_page` (`GET /reference-versions`) to return a redirect to `/configuration` instead of rendering the standalone page (FR-013a, C-API-2).
- [X] T032 [P] [US5] In `src/asset_dashboard/web/i18n.py`, add any Configuration subtab label keys (e.g. `configuration.subtab_users_sessions`, `configuration.subtab_scripts_versions`) in Ukrainian; reference from the template (FR-017).

**Checkpoint**: Configuration is role-aware with two admin subtabs and the folded-in version dictionary.

---

## Phase 8: Polish & Cross-Cutting

- [X] T033 [P] Run `python -m pytest tests/unit/test_i18n_help_coverage.py -q` and fix any missing/dangling catalog keys introduced by the edits (FR-017).
- [X] T034 Run the full suite `python -m pytest -q`; fix regressions (esp. role-based access-control and any rendered-HTML assertions on changed pages).
- [ ] T035 [P] (automated equivalents green; live-browser visual pass still recommended) Manual pass of `specs/006-ui-layout-refinements/quickstart.md` on desktop AND ~375px width: verify every ✅ item (two-column stacking with no horizontal scroll, preview placeholder, resizable ports, subtab state retention, operator view, redirect).
- [X] T036 [P] Grep the codebase for any lingering references to the removed nav link / columns / `/reference-versions` page link (templates, tests, docs) and clean up.

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (P1)**: no deps.
- **Foundational (P2: T003)**: after Setup; blocks US1 and US2 (Home layout).
- **US1 (P3)**: after Foundational. MVP.
- **US2 (P4)**: after US1 (renders into the left column from T006) + Foundational.
- **US3 (P5)**: after Setup; independent of Home stories (can run in parallel with US1/US2).
- **US4 (P6)**: after Setup; fully independent.
- **US5 (P7)**: after Setup; independent of US1–US4.
- **Polish (P8)**: after all targeted stories.

### Story independence

- US3, US4, US5 touch disjoint files from US1/US2 and from each other → parallelizable across developers.
- US2 is the only cross-story dependency (depends on US1's Home markup).

### Within a story

- Write the test task(s) first (expect fail) → implementation → re-run.
- Template edits before i18n key removals (so you know which keys are unused).

---

## Parallel Opportunities

- **Setup**: T002 ∥ T001-followup.
- **After Foundational**, three tracks can run in parallel:
  - Track A: US1 → US2 (Home).
  - Track B: US3 (editor + preview).
  - Track C: US4 (tables) and US5 (configuration) — themselves independent.
- Test tasks marked [P] within a story run together.
- i18n-only tasks (T008, T012, T021, T032) are [P] relative to their template siblings but must be sequenced after the template edits that determine key usage.

### Parallel example (post-Foundational)

```text
Developer A: T004→T008 (US1), then T009→T012 (US2)
Developer B: T013→T017 (US3)
Developer C: T018→T021 (US4), then T022→T032 (US5)
```

---

## Implementation Strategy

### MVP first

1. Setup (T001–T002) → Foundational (T003) → US1 (T004–T008).
2. **STOP & VALIDATE**: Home decluttered + two-column + scan columns trimmed. Demo.

### Incremental delivery

US1 (MVP) → US2 → US3 → US5 → US4, validating each independently. (US4 is lowest priority/risk; order among P2 stories is flexible.)

---

## Notes

- Pure UI feature: **no DB migration, no new entity, no new HTTP endpoint** (only a redirect + a view read-model + relaxed preview validation).
- Keep all user-facing strings in `web/i18n.py`; no hard-coded Ukrainian literals (FR-017).
- Server-side role gating (`require_admin`) stays authoritative; UI hiding is cosmetic (FR-015, Constitution VII).
- Commit after each task or logical group; stop at any checkpoint to validate a story.

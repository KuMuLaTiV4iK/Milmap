# UI & Backend-Delta Contract: UI Layout Refinements

This feature is primarily UI. The "contract" is the observable per-view behavior plus the two small backend deltas and one redirect. Each item cites the FR it satisfies and is paired with a check in `quickstart.md`.

## Backend deltas (the only server behavior changes)

### C-API-1: Preview command tolerates an empty target (FR-008, FR-009)

- **Endpoint**: `POST /api/profiles/preview-command` (existing).
- **Change**: validate with `require_target=False`; when `target_scope` is empty, build the preview against a placeholder target token so the response `display` is a complete command string, never blank and never a validation error for the missing target only.
- **Contract**:
  - Request `{ name, target_scope: [], port_spec, scan_params, extracted_fields, selected_scripts }` → `200` with `{ command: [...], display: "nmap ... <placeholder> ..." }`.
  - Request with a valid non-empty `target_scope` → unchanged behavior (same command the runner would execute).
  - Other validation errors (bad port spec, non-allowlisted script, bad timing) → still `422`/validation error as today.
- **Non-goal**: create/update/run endpoints are NOT relaxed; they keep their existing target rules.

### C-API-2: Standalone reference-versions page redirects (FR-013a)

- **Endpoint**: `GET /reference-versions` (existing page route).
- **Change**: respond with a redirect to `/configuration` (e.g. `307`/`302`) instead of rendering a standalone page.
- **Contract**: any client hitting `/reference-versions` lands on `/configuration`; the version dictionary is managed there. The `/api/reference-versions` CRUD endpoints are unchanged and remain operator-accessible.

### C-API-3: Home view exposes upcoming schedules (FR-003, FR-004)

- **View**: `GET /` (`web/dashboard.py`).
- **Change**: context gains `upcoming_schedules`: up to 5 enabled `Schedule`s ordered by `next_run_at` ascending, each `{ id, profile_name, label, next_run_at }`.
- **Contract**: with ≥1 enabled schedule, the Home response contains a schedules section listing them (≤5, soonest-first); with none, it renders the empty state. No new HTTP endpoint is added.

## Per-view UI contract

### C-HOME — Home page (`dashboard.html`) — FR-001..FR-006

| ID | Requirement | Observable check |
|----|-------------|------------------|
| C-HOME-1 | No "Головна" heading, no "Останні профілі…" subtitle (FR-001) | Neither `dashboard.title` as an `<h1>` nor `dashboard.subtitle` text appears on `/`. |
| C-HOME-2 | Two-column layout: profiles left, scans right (FR-002) | A `.home-columns` container has a left column (profiles) and right column (scans) on desktop width. |
| C-HOME-3 | Upcoming schedules under profiles, left column (FR-003) | Up to 5 schedule rows render beneath the profiles card, ordered soonest `next_run_at` first. |
| C-HOME-4 | Each schedule row links to Schedules (FR-004) | Activating a row navigates to `/schedules` (anchor or clickable row with keyboard support). |
| C-HOME-5 | Recent-scans drops 3 columns, keeps non-compliant (FR-005) | No "Відповідає"/"Невідомо"/"Непереконливо" headers; "Профіль", "Останній запуск", "Не відповідає", actions remain. |
| C-HOME-6 | Empty states, no errors (FR-006) | With zero profiles / scans / schedules, each section shows its empty message and the page still renders 200. |
| C-HOME-7 | Narrow width, no horizontal scroll (SC-008) | At ~375px the two columns stack; no horizontal page scrollbar. |

### C-PROF — Profiles list (`profiles_list.html`, `_macros.html`) — FR-007

| ID | Requirement | Observable check |
|----|-------------|------------------|
| C-PROF-1 | "Розклад" column removed | No `profiles.col_schedule` header; `profile_row` renders no schedule `<td>`; remaining columns unaffected; empty-row colspan updated. |

### C-EDIT — Profile editor (`profile_editor.html`) — FR-008..FR-010

| ID | Requirement | Observable check |
|----|-------------|------------------|
| C-EDIT-1 | Command preview visible with empty target (FR-008) | On a fresh "new profile" form (no target), `#command-preview` shows an `nmap …`-style command containing the placeholder, not the literal fallback `nmap …`. |
| C-EDIT-2 | Preview updates when target entered (FR-009) | Typing a target replaces the placeholder with the real target in the preview. |
| C-EDIT-3 | Ports field shows full contents (FR-010) | `#port_spec` is a resizable/multi-line control; a 20+ entry comma list is fully visible without clipping; value still validates. |

### C-HIST — History (`history.html`) — FR-011

| ID | Requirement | Observable check |
|----|-------------|------------------|
| C-HIST-1 | "З кешу?" column removed | No `history.col_cached` header; no per-row cache cell; remaining columns unaffected; empty-row colspan updated. |

### C-CFG — Configuration (`configuration.html`, `base.html`) — FR-012..FR-016

| ID | Requirement | Observable check |
|----|-------------|------------------|
| C-CFG-1 | Admin sees two subtabs with correct grouping (FR-012) | As admin: Subtab 1 = Users + Security settings; Subtab 2 = NSE allow-list + Version dictionary. |
| C-CFG-2 | Subtab switch has no reload / no lost state (FR-016) | Switching subtabs is in-page (no navigation); form field values entered in the other subtab persist. |
| C-CFG-3 | Version dictionary reachable in Subtab 2 (FR-013) | The reference-versions table + add/edit/delete controls render within Configuration Subtab 2. |
| C-CFG-4 | Standalone nav entry removed (FR-013a) | `base.html` nav no longer shows "Довідник версій"; `/reference-versions` redirects to `/configuration`. |
| C-CFG-5 | Operator reduced view (FR-014) | As operator: only own-password card + version-dictionary card visible; no users / security / NSE controls in the DOM. |
| C-CFG-6 | Server-side role enforcement intact (FR-015, SC-007) | As operator, `GET/POST/PUT/DELETE` to `/api/users`, `/api/settings/security`, `/api/nse-scripts` return 403; `/api/reference-versions` succeeds. |

## i18n contract (FR-017)

- Every new/changed visible string resolves through `t(key)` in `web/i18n.py`; no hard-coded Ukrainian literal added to templates.
- `tests/unit/test_i18n_help_coverage.py` stays green (no referenced control id loses its help entry; no template references a missing key).

## Out of scope (explicit)

- No change to scan execution, compliance evaluation, credential tool, scheduling engine, auth, or audit semantics.
- No new persisted data; no migration.

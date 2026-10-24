# Phase 0 Research: Home Page & Results Corrections

All decisions below are grounded in the existing codebase (features 001/002).
No `NEEDS CLARIFICATION` remained after `/speckit-clarify` (6 clarifications
recorded in spec.md). No new runtime dependencies are introduced (Principle I).

## US3 — Ports column defect (root cause + fix)

**Decision**: Stop discarding port `state` in `discovery/runner._persist_assets`,
and choose the rendering mode from the number of ports in the run's results.

- **Rationale**: `discovery/parser.ParsedPort` already carries `state`
  (`open`/`filtered`/`closed`), but `_persist_assets` builds each stored port
  dict as `{"port","protocol","service","version"}` — **no `state`** — and copies
  *all* `host.ports` regardless of state. The template then renders every entry as
  if open. The fix is purely downstream of the parser: add `"state": p.state` to
  each stored port dict, record a run-level `summary["ports_in_results"]` count,
  and let the view decide presentation.
- **Scan-size count**: per the clarification, the small/large threshold uses the
  **actual number of ports present in the scan's results** (not the profile's
  port spec). Computed as the count of distinct `(port, protocol)` pairs across
  the run's parsed hosts, stored in `DiscoveryRun.summary["ports_in_results"]`.
  `≤10` → small (show every port with state), `>10` → large (open-only; if a
  responding host has no open ports, show "Всі порти closed або filtered").
- **Service version (FR-011)**: derive from an **open** port only —
  `next((p.version for p in host.ports if p.state == "open" and p.version), None)`.
- **Rendering**: a small helper `discovery/results_view.py` produces the per-row
  port-display model (mode + list of `{port,protocol,state,service}` or the
  all-closed placeholder); `run_detail.html` consumes it. Keeps template logic
  thin and unit-testable without a browser.
- **Historical rows**: runs recorded before this change have port dicts without
  `state`; the view treats a missing `state` as `open` (prior behavior) so old
  runs render unchanged. No backfill migration needed (JSON column).
- **Alternatives considered**: a new `ports` table (rejected — YAGNI; JSON column
  already holds the data); storing only open ports (rejected — small-scan view
  needs filtered/closed states too).

## US1 — Home page + target-less profiles

**Decision**: Rework `web/dashboard.py` into a Home page with two bounded
sections; make `target_scope` optional at save and injectable at launch.

- **Home query**: recent profiles = top 5 `DiscoveryProfile` by `updated_at` desc
  (fallback `created_at`), independent of `compliance_settings`. Recent scans =
  top 20 `DiscoveryRun` across all profiles by `started_at` desc; posture tally
  from findings when the run evaluated `version_validity`, else "not applicable".
- **"Run now"** reuses `POST /api/profiles/{id}/runs`. For a target-less profile
  the client prompts for a target and sends it in the request body.
- **Target optional at save (FR-003a)**: `validate_target_scope` currently
  rejects an empty list. Add a `require_target: bool = True` parameter threaded
  through `validate_profile`; profile create/update pass `require_target=False`
  (empty allowed; a *present* target is still validated). The run path requires a
  non-empty effective target.
- **Launch-time target (FR-003b/c/d)**: `StartRunRequest` gains optional
  `target_scope: list[str] | None`. `api_start_run` resolves the effective target
  = override if provided else the profile's saved target; if empty → `400`
  "target required". A provided override is validated with `validate_target_scope`
  (same rules). `discovery.runner.start_run` gains `target_override: list[str] |
  None`; when set, `params_used["target_scope"]` uses it — the override is **never
  written back to the profile row** (ephemeral, FR-003c).
- **Cache interaction**: when a target override is supplied, skip the fresh-cache
  path (treat as `force_fresh`) so a cached run for a *different* target is never
  served. Documented so cache keys need not grow a target dimension.
- **Profiles-list parity (clarification)**: the profiles-list "Run" uses the same
  endpoint and the same target prompt for target-less profiles — no dead end.
- **Alternatives considered**: a nullable `target_scope` column (rejected — it is
  already a JSON list defaulting to `[]`; "empty" is the natural target-less
  state, no DDL needed).

## US2 — Dynamic UI without manual reload

**Decision**: Use the already-vendored HTMX; return HTML fragments / do row-level
swaps for profile mutations.

- **Rationale**: HTMX is already in the stack (002). Duplicate → `hx-post` the
  duplicate endpoint and append the new row (`hx-swap=beforeend` on the table
  body, server returns a `<tr>` fragment). Delete → `hx-delete` and remove the row
  (`hx-swap=outerHTML`/`delete` on the row). Create/edit already redirect back to
  the list, which re-renders fresh.
- **Failure (FR-008)**: on a non-2xx response HTMX does not swap; a small inline
  error region (via `hx-target` for errors or an `HX-Trigger` toast) shows the
  failure, leaving the list consistent with server state.
- **Scope**: applies to in-page lists updated after a user-initiated mutation
  (profiles list is the concrete instance), not passive live-streaming of other
  sessions' changes (per spec Assumptions).
- **Alternatives considered**: full client framework (rejected — Principle VI, no
  new deps); full-page reload after mutation (rejected — this is the defect).

## US4 — Non-compliant remediation + reference-versions view

**Decision**: Extend the version check to attach the expected valid entry;
highlight non-compliant rows in orange; add an in-app reference-versions view
that both roles can edit, audit-logged.

- **Expected valid version (FR-013)**: `compliance/version_check.check_version`
  returns, on an `invalid` match, an additional `expected_valid` built from the
  first `valid` `ReferenceVersionEntry` with the same `product` (plus the invalid
  entry's `note`). When no valid entry exists, carry only the note — do **not**
  invent a version (edge case). `evaluate.py` stores this in `finding.detail`.
- **Orange row (FR-012/FR-014)**: `run_detail.html` adds a `row-non-compliant`
  class when any finding `result == non_compliant`; `base.css` defines the orange
  token from the existing dark SOC palette. Compliant/unknown rows get no class.
- **Reference-versions view (FR-015/FR-015a/FR-015b)**: new `reference_versions/`
  package — `service.py` (list/create/update/delete `ReferenceVersionEntry`) and
  `routes.py` (a page listing vendor/product/version_match/status/note plus inline
  add/edit/remove). Editable by **Operators and Administrators** (session-auth
  only, no `require_admin`): the version-validity reference dataset is operational
  compliance data, not a Principle VII admin-only surface. Every edit calls
  `record_event(..., CONFIG_CHANGE, detail={...})` (FR-015b).
- **Alternatives considered**: admin-only editing (rejected per clarification);
  separate "expected version" table (rejected — the valid/invalid rows already
  encode it).

## US5 — NSE scripts list control

**Decision**: Replace the NSE checklist in `profile_editor.html` with a
multi-select list/`<select multiple>` (or searchable dropdown) populated from the
enabled allow-list; presentation only.

- **Rationale**: Allow-list source (`nse/allowlist.enabled_script_ids`),
  persistence (`DiscoveryProfile.selected_scripts`), validation
  (`validate_selected_scripts`), and command composition (`build_nmap_command`)
  are unchanged — only the control markup changes. A stale selection (script
  later disabled) still fails save validation exactly as today.
- **Alternatives considered**: a JS multiselect library (rejected — no new deps;
  native `<select multiple>` + light styling suffices).

## US6 — Schedule profile scans (own target, multiple per profile, from history)

**Decision**: Extend the existing `Schedule` model + `scheduling/engine.tick()`
rather than add a new scheduler or tool type (Principle VI).

- **Existing state**: `Schedule` (one row per profile, `UNIQUE(profile_id)`),
  `scheduling/routes.py` (upsert/get/delete per profile), `schedules.html`, and
  `tick()` already run due profile schedules via `start_run(session, profile)`.
  What is missing is (a) multiple schedules per profile, (b) a per-schedule
  target, and (c) creating a schedule from a past run.
- **Schema (migration 0003)**: add `Schedule.target_scope` (JSON, the schedule's
  own target) and an optional `Schedule.label`; **drop `UNIQUE(profile_id)`** so a
  profile may have several schedules. Under SQLite this needs an Alembic **batch**
  migration (table rebuild) — SQLite cannot drop a constraint in place.
- **Target ownership (FR-021a)**: each schedule stores its own `target_scope`, set
  at creation (defaulting to the profile's saved target when it has one) and used
  for every run. `tick()` passes `target_override=schedule.target_scope` into
  `start_run` (the same override added for US1). A later change to the profile's
  saved target does not touch existing schedules.
- **Validation (FR-021b)**: schedule create/update validates `target_scope` with
  `validate_target_scope` (non-empty, well-formed) — a schedule can never run with
  an empty/invalid target, which also closes the target-less-profile gap.
- **Routes**: generalize `scheduling/routes.py` to CRUD by `schedule_id`
  (`GET/POST /api/profiles/{id}/schedules`, `PUT/DELETE
  /api/schedules/{schedule_id}`) carrying `target_scope` + `label`. Add
  `POST /api/runs/{run_id}/schedule` (create-from-history): copies the run's
  profile and `params_used.target_scope` onto a new schedule.
- **No-duplicate-concurrent-run (FR-022)**: unchanged — `start_run` still raises
  `AlreadyRunningError`; `tick()` already honors overlap policy. Scheduled runs
  are recorded in history/audit identically to manual (existing behavior).
- **Profile deletion**: `Schedule.profile_id` FK is `ON DELETE CASCADE`; deleting
  a profile removes its schedules (edge case) — preserved.
- **Alternatives considered**: a second schedule table or a generic "scan task"
  mirroring `ToolTask` (rejected — `Schedule` already models profile recurrence;
  adding a target column is the minimal change); embedding the schedule in the
  profile (rejected — the spec requires schedules independent of profile edits).

## Cross-cutting

- **i18n**: `web/i18n.py` gains/renames keys so the heading and nav read
  "Головна" (FR-001), plus strings for the recent-scans overview, the
  all-closed ports placeholder, remediation labels, the reference-versions view,
  and per-schedule target/label. Single Ukrainian locale (Principle VI).
- **Testing**: existing 001/002 suites must stay green (SC-008). New tests are
  added per user story (see plan Testing).

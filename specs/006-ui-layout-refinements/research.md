# Phase 0 Research: UI Layout Refinements

No open `NEEDS CLARIFICATION` items remained after `/speckit-clarify` (nav treatment, scan columns, and schedule ordering were all resolved). Research here records the decisions that shape the template/view edits and the two small backend touches, grounded in the current code.

## R1 — Home two-column layout (FR-002, SC-008)

- **Decision**: Wrap the Home content in a flex/grid container (`.home-columns`) with two children: a left column (recent profiles card + upcoming schedules card) and a right column (recent scans card). Collapse to a single stacked column below ~900px via a media query. Implement in `static/base.css`; reorder markup in `dashboard.html`.
- **Rationale**: The app is server-rendered with plain CSS and no framework; a CSS grid/flex wrapper is the simplest, dependency-free way to get a responsive two-column split with no horizontal scroll. Matches constitution Principle VI (simplicity) and I (no new assets).
- **Alternatives considered**: A JS layout library (rejected — unnecessary, violates offline/simplicity); a `<table>`-based two-column shell (rejected — abuses tables for layout, worse at narrow widths).

## R2 — Upcoming schedules on Home (FR-003, FR-004, US2)

- **Decision**: Add a read-model in `web/dashboard.py`: `session.query(Schedule).filter_by(enabled=True).order_by(Schedule.next_run_at.asc()).limit(5)`, resolve each schedule's profile name/label, and pass a `upcoming_schedules` list to the template. Each row renders as a link to `/schedules`.
- **Rationale**: Clarification chose "by next scheduled run, soonest first". `Schedule.next_run_at` already exists and is indexed via the schedule's natural ordering use; `enabled` filter avoids surfacing paused schedules as "upcoming". The `/schedules` page already exists — no new endpoint (Principle VI).
- **Open sub-decision (low impact, defer to tasks)**: whether to include disabled schedules. Chosen: exclude disabled (they have no meaningful "next run"). Row label = schedule `label` if set, else profile name.
- **Alternatives considered**: Ordering by creation or last run (rejected per clarification); a new `/api/schedules/upcoming` endpoint (rejected — the page view can query directly, matching how `recent_profiles`/`recent_scans` are already built in the same file).

## R3 — Recent-scans column removal (FR-005, A-002)

- **Decision**: In `dashboard.html`, remove the three `<th>`/`<td>` pairs for `dashboard.col_compliant` (Відповідає), `dashboard.col_unknown` (Невідомо), `dashboard.col_inconclusive` (Непереконливо). Keep `dashboard.col_non_compliant` (Не відповідає). Update the `{% if scan.evaluated %}` branch's `colspan` (currently 4 → becomes 1) and the empty-row `colspan` (currently 7 → becomes 4).
- **Rationale**: Clarification kept only the non-compliant signal. The posture `Counter` still computes all values; we simply stop rendering three of them, so no view-logic change is needed beyond the template.
- **Alternatives considered**: Removing all compliance columns (rejected per clarification); stripping the posture computation in the view (rejected — unnecessary churn, the Counter is cheap and other logic reads `evaluated`).

## R4 — Preview command with no target (FR-008, FR-009)

- **Decision**: In `profiles/routes.py::api_preview_command`, call `validate_profile(payload, allowlisted_script_ids=..., require_target=False)`. When `body.target_scope` is empty, build the command against a single placeholder token (e.g. `["<ціль>"]`) so `build_nmap_command` yields a complete, readable preview; otherwise use the real target unchanged.
- **Rationale**: Today the endpoint validates with the default `require_target=True`, so an empty target returns a validation error and the UI falls back to the literal `nmap …`. Preview is non-executing, so relaxing `require_target` there is safe and does not touch the create/update/run paths (which keep their own target rules). The placeholder makes the absent target visible rather than producing a malformed/targetless command string. Preview/execution parity is preserved for real targets because the same `build_nmap_command` is used.
- **Alternatives considered**: Building client-side in JS (rejected — would duplicate the server command builder and risk divergence, the very thing the shared builder prevents); returning the raw targetless command (rejected — ambiguous/empty preview, fails FR-008's "clearly-marked placeholder").

## R5 — Ports field shows full contents (FR-010, SC-004)

- **Decision**: Replace the single-line `<input id="port_spec">` in `profile_editor.html` with a full-width, vertically resizable `<textarea id="port_spec">` (small default height, `resize: vertical`, wraps). On read (`readForm`), strip whitespace/newlines before sending so the existing `_PORT_SPEC_RE` validation (no spaces allowed) still passes.
- **Rationale**: A long comma-separated port list overflows a single-line input (the reported bug). A textarea uses the available vertical space and wraps. Minimal JS change (one `.replace(/\s+/g,'')` on read). Keeps server-side `validate_port_spec` unchanged.
- **Alternatives considered**: Auto-growing single-line input via JS (rejected — more JS, still awkward for very long lists); only widening the input (rejected — does not solve multi-line visibility). A textarea is the simplest robust fix.

## R6 — Configuration subtabs + role-aware view (FR-012–FR-016, FR-014, FR-015)

- **Decision**: Render Configuration differently by role (`session_role` already in context):
  - **Administrator**: an in-page two-tab control (plain CSS/JS toggle, no routing). Subtab 1 holds the Users card + Security settings card; Subtab 2 holds the NSE allow-list card + the Version dictionary card.
  - **Operator**: a flat page with only the own-password card + the Version dictionary card (no subtab chrome, no admin cards).
- **Rationale**: The admin-only cards are already wrapped in `{% if session_role == 'administrator' %}`; we keep that gate and add the subtab wrapper inside it. Server-side `require_admin` on the users/security/NSE APIs stays authoritative (FR-015), so hiding is purely cosmetic. Operators already have `require_operator` access to the reference-versions API, so surfacing the version-dictionary card to them grants no new capability (Principle VII).
- **Sub-decision — subtab mechanism**: a small inline JS toggler showing/hiding two `<section>`s (and remembering nothing across reloads). FR-016 ("don't lose unsaved context on switch") is naturally satisfied because switching is pure show/hide, not navigation/reload.
- **Alternatives considered**: Separate routes per subtab (rejected — adds routes, causes reloads that could drop form state, violates FR-016 intent and Principle VI); HTMX partial swaps (rejected — unnecessary round-trips for a pure view toggle).

## R7 — Version dictionary relocation & anti-strand (FR-013, FR-013a, A-001, edge case)

- **Decision**: Move the reference-versions management UI (the table + add/edit/delete form and its JS, from `reference_versions.html`) into `configuration.html` Subtab 2 (admin) and the operator flat view. Extract the shared markup into a partial (e.g. `_reference_versions.html` or a `_macros.html` macro) so it is defined once and included in both configuration and (optionally) the legacy page. Remove the `nav.reference_versions` link from `base.html`. Redirect the standalone `/reference-versions` GET to `/configuration`.
- **Rationale**: Clarification said remove the standalone nav link; version dictionary reachable only via Configuration. A server redirect on the old path prevents stranding bookmarks (spec edge case) without keeping a second linked surface. The reference-versions API endpoints are unchanged, so the embedded UI keeps working for both roles.
- **Alternatives considered**: Keep both surfaces (rejected per clarification); delete the `/reference-versions` route entirely (rejected — 404s any existing bookmark; redirect is friendlier and cheap).

## R8 — i18n catalog impact (FR-017)

- **Decision**: All new/changed user-facing text routes through `web/i18n.py` `STRINGS`. Add keys for the upcoming-schedules section (title, empty state, row label formatting) and any Configuration subtab labels; stop rendering `dashboard.title`/`dashboard.subtitle` on Home (keys may remain in the catalog but unused on that page). Keep `history.col_cached`, `profiles.col_schedule`, and the removed `dashboard.col_*` keys in the catalog if still referenced elsewhere; remove only truly-unused keys to avoid breaking `test_i18n_help_coverage`.
- **Rationale**: Single-locale catalog is the project standard; no hard-coded literals (Principle I/VI). Leaving now-unused keys is harmless and safer than risking a coverage-test break; removal is optional cleanup verified against references.
- **Alternatives considered**: Inline Ukrainian literals in templates (rejected — violates FR-017 and project i18n convention).

## Summary of backend-touch surface (everything else is template/CSS)

1. `web/dashboard.py` — add `upcoming_schedules` read-model (query + context key).
2. `profiles/routes.py::api_preview_command` — `require_target=False` + placeholder target when empty.
3. `reference_versions/routes.py` — `/reference-versions` page redirects to `/configuration`.

No model, migration, or new endpoint is introduced.

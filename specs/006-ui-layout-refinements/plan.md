# Implementation Plan: UI Layout Refinements

**Branch**: `006-ui-layout-refinements` | **Date**: 2026-10-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/006-ui-layout-refinements/spec.md`

## Summary

A presentation-layer refinement of the existing Milmap dashboard. It declutters the Home page (drop the heading/subtitle, two-column profiles/scans layout, a "next 5 schedules" list that links to the Schedules page, and three compliance columns removed from recent scans), simplifies the Profiles and History tables (drop the "Розклад" and "З кешу?" columns), fixes the profile editor (command preview visible with no target; a ports field that shows its full contents), and reorganizes the Configuration page into two role-aware subtabs that fold the version dictionary ("Довідник версій") in and remove its standalone nav entry.

Technical approach: almost entirely Jinja template + CSS + small inline-JS edits against the existing FastAPI server-rendered app. Two small backend touches are required and nothing else: (1) the Home view (`web/dashboard.py`) gains a query for the 5 soonest-upcoming enabled schedules; (2) the profile-preview endpoint (`profiles/routes.py::api_preview_command`) must validate with `require_target=False` and substitute a visible placeholder for an empty target so the preview renders. No database schema change, no new entity, no new persisted data.

## Technical Context

**Language/Version**: Python 3.13+ (project targets 3.13/3.15 per repo), server-rendered Jinja2 templates + vanilla JS (no frontend framework).

**Primary Dependencies**: FastAPI, Starlette/Jinja2 templating (`web/templating.py`), SQLAlchemy ORM, HTMX (`/static/htmx.min.js`, vendored). Single-locale Ukrainian catalog in `web/i18n.py` (no gettext/Babel).

**Storage**: SQLite via SQLAlchemy under local `data/`. **No schema change in this feature.**

**Testing**: pytest. Existing suites include template/route tests and `tests/unit/test_i18n_help_coverage.py` (catalog contract). New/updated tests cover the view query, the preview-with-no-target behavior, column removals, and role-gated Configuration rendering.

**Target Platform**: Single-host, air-gapped internal web app; modern evergreen browser on desktop, usable at narrow widths.

**Project Type**: Web application (server-rendered), single project tree under `src/asset_dashboard/`.

**Performance Goals**: No new performance-sensitive paths. The added Home query is a single indexed `ORDER BY next_run_at LIMIT 5`. Page render budget unchanged (sub-200ms server render for the dashboard at the stated ~5,000-host / modest-schedule scale).

**Constraints**: Offline/air-gapped — no new CDN/network assets; all CSS/JS inline or already vendored. All user-facing strings go through the `t()` catalog (no new hard-coded literals). No horizontal page scroll at narrow widths. Server-side role enforcement must remain authoritative (UI hiding is cosmetic only).

**Scale/Scope**: 4 pages touched (Home, Profiles, History, Configuration), 1 shared macro, 1 editor page, the i18n catalog, 2 view/route files, base-nav. ~No data migration.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Impact | Status |
|-----------|--------|--------|
| I. Offline-First / Air-Gapped | No new external assets; CSS/JS stay inline or vendored; no network calls added. | ✅ PASS |
| II. Security by Default | No change to auth, sessions, password policy, or secret handling. Configuration remains behind an authenticated session. | ✅ PASS |
| III. Device-Safety Invariants | Untouched — this feature does not alter the credential check or any active probe. | ✅ PASS (N/A) |
| IV. Auditability | No change to audited actions. Relocating version-dictionary management keeps its existing `CONFIG_CHANGE` audit events intact. | ✅ PASS |
| V. Testable & Independently Deliverable | Each user story is an independent slice with its own acceptance checks; CI invariant suite (incl. role-based access control) must stay green. | ✅ PASS |
| VI. Simplicity (YAGNI) | Template/CSS edits + two tiny view touches; no new components, routes beyond a redirect, or data. Reuses the existing schedule and reference-version APIs. | ✅ PASS |
| VII. Least-Privilege Roles | Operators gain no admin capability. Admin-only Configuration controls (users, security settings, NSE allow-list) stay `require_admin` server-side AND hidden; operators keep own-credentials + version-dictionary (already operator-accessible via `require_operator`). | ✅ PASS |

**Initial gate: PASS.** No violations; Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/006-ui-layout-refinements/
├── plan.md              # This file
├── spec.md              # Feature specification (with Clarifications)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (no schema change; read-models only)
├── quickstart.md        # Phase 1 output (manual + automated validation)
├── contracts/
│   └── ui-contract.md   # Phase 1 output (per-view UI/behavior contract + the 2 backend deltas)
└── checklists/
    └── requirements.md  # From /speckit-specify + /speckit-clarify
```

### Source Code (repository root)

```text
src/asset_dashboard/
├── web/
│   ├── dashboard.py                 # Home view — ADD "upcoming schedules" read-model
│   ├── i18n.py                      # STRINGS catalog — add/adjust keys; remove dashboard.subtitle usage
│   └── templates/
│       ├── base.html                # Nav — REMOVE standalone "Довідник версій" link
│       ├── dashboard.html           # Home — remove heading/subtitle, 2-col layout, schedules list, drop 3 scan cols
│       ├── profiles_list.html       # Profiles table — drop "Розклад" column
│       ├── history.html             # History table — drop "З кешу?" column
│       ├── profile_editor.html      # Ports field → resizable; preview works with no target
│       ├── configuration.html       # Two subtabs (admin) / reduced view (operator) + fold-in version dictionary
│       ├── reference_versions.html  # Source of the version-dictionary partial (reused inside configuration)
│       └── _macros.html             # profile_row — drop schedule cell; (optional) schedule-row / version-table partial
├── profiles/
│   └── routes.py                    # api_preview_command — require_target=False + placeholder target
└── reference_versions/
    └── routes.py                    # /reference-versions page → redirect to /configuration (anti-strand)

tests/
├── unit/ and integration/          # update column/nav assertions; add preview-no-target, upcoming-schedules, role-view tests
```

**Structure Decision**: Existing single-project, server-rendered layout is kept as-is. All changes live in the current `web/templates`, `web/dashboard.py`, `web/i18n.py`, `profiles/routes.py`, and `reference_versions/routes.py`. No new packages or directories.

## Key Design Decisions (detail in research.md)

1. **Home two-column layout** — CSS flro/grid wrapper (`.home-columns`) in `base.css`; left column stacks profiles + upcoming-schedules cards, right column holds recent scans. Collapses to single column under a max-width media query (no horizontal scroll). Pure CSS; markup reordered in `dashboard.html`.
2. **Upcoming schedules on Home** — new read-model in `dashboard.py`: enabled `Schedule` rows ordered by `next_run_at` ascending, limit 5, joined to profile name/label. Each row is a link to `/schedules`. Reuses the existing `Schedule` model and `/schedules` page; no new endpoint.
3. **Recent-scans columns** — remove the "Відповідає" (compliant), "Невідомо" (unknown), "Непереконливо" (inconclusive) cells/headers; keep "Не відповідає" (non-compliant). Adjust the `compliance_na` colspan accordingly.
4. **Preview without target (FR-008/FR-009)** — in `api_preview_command`, validate with `require_target=False`; when `target_scope` is empty, build the command against a single visible placeholder token (e.g. `<ціль>`) so the preview is never blank. Execution/save paths are untouched (still `require_target` per existing save rules), so preview/execution parity holds for real targets.
5. **Ports field (FR-010)** — convert the single-line `#port_spec` `<input>` to a `<textarea>` (full width, `resize: vertical`, small default rows) OR a full-width auto-expanding input; value read logic (`readForm`) unchanged since it reads `.value`. Keep validation regex intact (strip newlines on read if textarea is used).
6. **Configuration subtabs (FR-012–FR-016)** — in-page tab toggle (no new routes) rendered only for Administrators: Subtab 1 = Users + Security/Session settings; Subtab 2 = NSE allow-list + Version dictionary. Operators get a flat reduced view: own-password card + version-dictionary card only. All existing admin API gating (`require_admin`) stays authoritative.
7. **Version dictionary relocation (FR-013/FR-013a)** — move the reference-versions management markup/JS into `configuration.html` (reusing a shared partial from `reference_versions.html` where practical), remove the `nav.reference_versions` link from `base.html`, and redirect the standalone `/reference-versions` page to `/configuration` to avoid stranding bookmarks.

## Complexity Tracking

No constitution violations. Table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

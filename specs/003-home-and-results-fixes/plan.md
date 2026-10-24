# Implementation Plan: Home Page & Results Corrections

**Branch**: `003-home-and-results-fixes` | **Date**: 2026-10-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-home-and-results-fixes/spec.md`

## Summary

A third iteration on the air-gapped **Milmap** dashboard that fixes three
defects and adds two capabilities, all within the existing FastAPI + Jinja2/HTMX
+ SQLAlchemy/SQLite + APScheduler single process (no new runtime dependencies).

- **US1 — Home page (P1)**: replace the compliance-only landing panel with a
  genuinely useful "Головна" (Home) page showing the 5 most-recently-updated
  profiles (each with a "Run now" action) and a recent-scans overview of the 20
  most recent runs across **all** profiles (compliance posture shown when a run
  evaluated it, "not applicable" otherwise). Profiles may now be saved **without
  a target** and launched from Home (or the profiles list) by supplying the
  target at launch — target only, ports/params unchanged, target not persisted.
- **US2 — Dynamic UI (P2)**: profile duplicate/delete/create/edit update the
  affected list in place via HTMX, no manual reload; a failed mutation leaves the
  view consistent with server state and surfaces an error.
- **US3 — Ports column (P3)**: fix the defect where filtered/closed ports render
  as if open. Persist each port's **state**; for a scan whose results contain ≤10
  ports show every port with its state, for >10 show open-only, and for a large
  scan with no open ports show "Всі порти closed або filtered". Service version
  is taken from an **open** port only.
- **US4 — Non-compliant remediation (P3)**: orange-highlight non-compliant rows,
  surface the expected valid version / remediation note from the local reference
  dataset, and add an in-app, operator-and-admin-editable, audit-logged view of
  the reference-version dictionary.
- **US5 — NSE list control (P4)**: present the allow-listed NSE scripts through a
  multi-select list/drop-down in the profile editor; persistence, allow-list
  validation and command composition unchanged.
- **US6 — Schedule profile scans (P2)**: let a profile's scan run on a recurring
  schedule defined as an independent task. Each schedule **carries its own
  target** (so target-less profiles are schedulable and a profile may have
  several schedules); a schedule can also be created from a past scan in the run
  history. Served by the one existing scheduler (Principle VI), honoring the same
  no-duplicate-concurrent-run rule.

**Technical approach**: Extend the existing `src/asset_dashboard/` tree in place.
The run **parser already reads port state** — the fix is to stop discarding it in
`discovery/runner._persist_assets` and to derive the service version from an open
port. The `Schedule` model and `scheduling/engine.tick()` already drive profile
schedules; US6 relaxes the one-schedule-per-profile constraint, adds a per-
schedule `target_scope`, and threads a target override through `start_run`. A new
`reference_versions/` package adds the read+edit view. One Alembic migration
(`0003`) carries the schema deltas. UI work is concentrated in the Jinja
templates, the i18n catalog, and `base.css` (orange row token).

## Technical Context

**Language/Version**: Python 3.11+ (existing `.venv`; 3.15 per environment) — unchanged from features 001/002.

**Primary Dependencies** (all already vendored; **no new packages** — Principle I):
- Web: FastAPI, Uvicorn, Jinja2 (server-rendered), vendored HTMX
- Persistence: SQLAlchemy 2.x + SQLite; Alembic migrations (`migrations/`)
- Scheduling: APScheduler heartbeat calling the in-DB `tick()` (`scheduling/engine.py`)
- Discovery: system `nmap` via `subprocess`; stdlib `xml.etree` parse (`discovery/parser.py`)
- Validation: Pydantic v2
- Testing: pytest, pytest-asyncio, httpx test client

**Storage**: SQLite under `data/app.sqlite3`. Schema deltas (migration `0003`):
`schedules` gains a `target_scope` (JSON) and an optional `label`, and loses the
`UNIQUE` constraint on `profile_id` (multiple schedules per profile). No new
tables — `ReferenceVersionEntry`, `DiscoveryProfile`, `DiscoveredAsset`,
`DiscoveryRun` already exist. Per-port `state` is stored inside the existing
`DiscoveredAsset.open_ports` JSON (no DDL).

**Testing**: pytest unit (port-state persistence + small/large rendering choice,
open-port version selection, target-optional validation, schedule-target
validation, `tick()` with per-schedule target, next-run math unchanged) +
integration per user story (home page content & run-now, target-less launch from
Home and profiles list, dynamic duplicate/delete, ports column small vs large,
orange + expected-version + reference view, NSE list control, schedule
create/from-history/fire) + contract (new/changed HTTP endpoints). All existing
001/002 tests must continue to pass (SC-008).

**Target Platform**: Single host (Windows 11 confirmed; Linux supported) on an isolated/air-gapped segment; accessed via local browser.

**Project Type**: Web application (single ASGI deployable serving a server-rendered UI).

**Performance Goals**: No new scan-performance target. Home page and history views load < 3 s at ~5,000-host scale (parity with 001/002); recent lists are bounded (5 profiles, 20 scans).

**Constraints**:
- **Air-gapped**: no new dependencies; all new behavior is local DB + templates.
- **Device safety (NON-NEGOTIABLE)**: the credential tool is untouched; its guard is unaffected.
- **Security**: launch-time and per-schedule targets pass the *same* `validate_target_scope`; no free-form nmap flags introduced; only the target is settable at launch (ports/params come from the profile).
- **Auditability**: reference-version edits logged as `CONFIG_CHANGE`; schedule changes as `SCHEDULE_CHANGE`; scheduled/manual runs as `RUN_STARTED`/`RUN_FINISHED`.

**Scale/Scope**: Unchanged (~5,000-host inventory; a few concurrent operators). Single Ukrainian locale; two roles.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution v1.1.0. Evaluation of this feature:

| Principle | Compliance |
|---|---|
| I. Offline-First / Air-Gapped | No new deps; all changes are local DB, routes, templates, CSS. Version-validity check stays a local-only query. ✅ |
| II. Security by Default | Auth gate unchanged. Launch-time target and per-schedule target reuse `validate_target_scope` (no bypass); nmap command still composed only from allow-listed params/scripts — launch sets *only* the target. Reference-version editing is operational compliance data (not user mgmt, security settings, or the NSE allow-list), so it is not a Principle VII admin-only surface; it is still audit-logged. ✅ |
| III. Device-Safety Invariants (NON-NEGOTIABLE) | Credential tool and its central guard are entirely out of scope and unchanged. ✅ |
| IV. Auditability | Reference-version edits → `CONFIG_CHANGE`; schedule create/edit/delete → `SCHEDULE_CHANGE`; scheduled profile runs recorded identically to manual (`RUN_STARTED`/`RUN_FINISHED`). No secrets added to any detail. ✅ |
| V. Testable & Independently Deliverable | Each of US1–US6 maps to independently testable modules + its own integration test; existing invariant suite preserved (SC-008). ✅ |
| VI. Simplicity (YAGNI) | Reuses the single scheduler and the existing `Schedule` table (no second scheduler, no new tool type); fixes the parser/runner in place; adds one small `reference_versions/` package rather than a generic admin CRUD framework. ✅ |

**Operator-editable reference data note**: US clarification lets both Operators
and Administrators edit the reference-version dictionary. Principle VII reserves
*user management, account/session security settings, and the NSE allow-list* for
Administrators — the version-validity reference dataset is none of these; it is
operational compliance data the operator already acts on. Edits are audited
(`CONFIG_CHANGE`). Recorded here as a deliberate decision, not a violation.

**Gate result**: PASS (no violations; Complexity Tracking empty).

## Project Structure

### Documentation (this feature)

```text
specs/003-home-and-results-fixes/
├── plan.md              # This file (/speckit-plan output)
├── spec.md              # Feature specification (+ Clarifications)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (entity deltas)
├── quickstart.md        # Phase 1 output (validation guide)
├── contracts/
│   └── http-api-delta.md # New/changed HTTP endpoints vs features 001/002
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

Changes build on the existing `src/asset_dashboard/` tree. New files/dirs marked **[new]**; touched files marked **[mod]**.

```text
src/asset_dashboard/
├── discovery/
│   ├── runner.py                 # [mod] persist per-port `state`; service_version from an OPEN port;
│   │                             #       run.summary["ports_in_results"]; accept target override
│   ├── routes.py                 # [mod] StartRunRequest gains optional target_scope; require target
│   │                             #       at run; force-fresh when target overridden; results carry state
│   └── results_view.py           # [new] helper: scan-size (small/large) + per-row port rendering model
├── profiles/
│   ├── validation.py             # [mod] target optional at save (require_target flag) — still valid if present
│   └── routes.py                 # [mod] create/update allow empty target_scope
├── scheduling/
│   ├── engine.py                 # [mod] tick() passes schedule.target_scope as target override to start_run
│   └── routes.py                 # [mod] multiple schedules/profile; per-schedule target (+validate);
│   │                             #       list/create/update/delete by schedule_id; create-from-run endpoint
├── reference_versions/
│   ├── service.py                # [new] list/create/update/delete ReferenceVersionEntry (+expected-valid lookup)
│   └── routes.py                 # [new] reference-versions view + edit API/pages (operator+admin, audited)
├── compliance/
│   ├── version_check.py          # [mod] on "invalid", attach expected valid entry/note (remediation)
│   └── evaluate.py               # [mod] store remediation (expected_valid) in finding.detail
├── web/
│   ├── dashboard.py              # [mod] Home: 5 recent profiles + 20 recent scans across ALL profiles
│   ├── i18n.py                   # [mod] "Головна" title/nav; home/ports/reference/schedule strings
│   ├── static/base.css           # [mod] orange non-compliant row token
│   └── templates/
│       ├── base.html             # [mod] nav label "Головна"
│       ├── dashboard.html        # [mod] Home: recent profiles (Run now) + recent scans overview
│       ├── run_detail.html       # [mod] ports column small/large rendering; orange row; remediation cell
│       ├── history.html          # [mod] "schedule this scan" action per run
│       ├── profiles_list.html    # [mod] HTMX duplicate/delete in place; run-now (target prompt)
│       ├── profile_editor.html   # [mod] NSE multi-select list control; target optional hint
│       ├── schedules.html        # [mod] per-schedule target; multiple per profile; create/edit
│       └── reference_versions.html # [new] reference-version dictionary view + inline edit
└── main.py                       # [mod] register reference_versions routers

migrations/versions/
└── 0003_*.py                     # [new] schedules: +target_scope, +label, drop UNIQUE(profile_id) (batch op)

tests/
├── unit/                         # [mod/new] port-state persistence + size rendering, open-port version,
│                                 #           target-optional validation, schedule-target validation, tick w/ target
├── integration/                  # [new] test_us1_home, test_us1_targetless_launch, test_us2_dynamic,
│                                 #       test_us3_ports, test_us4_remediation_reference, test_us5_nse_list,
│                                 #       test_us6_schedule (+ from-history)
└── contract/                     # [mod/new] test_schedule (multi + target + from-run), test_reference_versions,
                                  #           test_runs (target override), test_profiles (target optional)
```

**Structure Decision**: Continue the single-project web application from
features 001/002. Prefer in-place fixes to the parser/runner and the existing
`Schedule`/scheduler over new machinery; add exactly one cohesive new package
(`reference_versions/`) and one render helper (`discovery/results_view.py`). This
keeps the deployment a single self-contained, air-gapped unit (Principle VI) and
lets each user story map to an independently testable module (Principle V).

## Complexity Tracking

> No constitution violations to justify. (Section intentionally empty.)
>
> Migration note (not a violation): dropping the `UNIQUE(profile_id)` constraint
> on `schedules` under SQLite requires an Alembic **batch** migration
> (table rebuild), since SQLite cannot drop a constraint in place.

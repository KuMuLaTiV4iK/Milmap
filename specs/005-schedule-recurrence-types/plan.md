# Implementation Plan: One-Time & Unit-Based Interval Schedules

**Branch**: `005-schedule-recurrence-types` | **Date**: 2026-10-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/005-schedule-recurrence-types/spec.md`

## Summary

Add a **once** (one-time) recurrence kind and replace the raw-seconds **interval** entry with a
"every N × unit" model (unit ∈ minute/hour/day/week/month) for discovery schedules. The work is
concentrated in the shared scheduling engine (`compute_next_run_at` + a new `validate_recurrence`,
plus one-shot handling in `tick()`), a small Ukrainian recurrence humanizer for display, and a
redesigned `/schedules` create **and edit** form. Editing reuses the existing
`PUT /api/schedules/{id}` endpoint — no new backend route — adding only a per-row Edit affordance
that pre-fills the form. Recurrence is already stored as JSON on the `Schedule` record,
and one-time completion reuses the existing `enabled`/`last_triggered_at` fields — **no database
migration is required**. Legacy recurrence shapes (`interval{seconds}`, `daily`, `weekly`) remain
valid in the engine so the standalone credential-tool tasks, which share this engine, keep working.

## Technical Context

**Language/Version**: Python 3.11+ (developed against 3.12/3.15)

**Primary Dependencies**: FastAPI, Jinja2 + HTMX, SQLAlchemy 2.x, APScheduler, Alembic — all already
present. **No new runtime dependency** (month arithmetic uses the standard library only).

**Storage**: SQLite (`data/app.sqlite3`). `Schedule.recurrence` and `ToolTask.recurrence` are JSON
columns; no new columns, no migration.

**Testing**: pytest (unit, integration, contract) against isolated temp SQLite DBs.

**Target Platform**: single air-gapped host; local browser on the same host as the server.

**Project Type**: Server-rendered web application (single project under `src/asset_dashboard/`).

**Performance Goals**: Not performance-sensitive — recurrence computation is O(1); the heartbeat runs
every ~30s over a handful of schedules.

**Constraints**: Fully offline, no network, no new dependency. Because the browser and server run on
the same host, local wall-clock time is shared between them.

**Scale/Scope**: Single operator, single host, a handful of schedules per profile.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Assessment |
|-----------|------------|
| I. Offline-First / Air-Gapped | ✅ No new dependency; month arithmetic via stdlib; zero network. |
| II. Security by Default | ✅ No auth/session change; `/schedules` stays behind the auth gate. |
| III. Device-Safety Invariants | ✅ Discovery schedules never run the credential check. The credential-tool tasks share `compute_next_run_at`; their attempt/cooldown caps live in the tool orchestrator and are untouched. FR-014 requires their recurrences keep working — covered by backward compatibility + a regression test. |
| IV. Auditability | ✅ `SCHEDULE_CHANGE` events on create/update/delete are preserved. |
| V. Testable & Independently Deliverable | ✅ US1/US2/US3 independently testable; new unit/integration/contract tests. |
| VI. Simplicity (YAGNI) | ✅ One scheduler engine extended in place — no second scheduler; legacy shapes kept with minimal code; single-locale catalog reused. |
| VII. Least-Privilege Roles | ✅ Scheduling is an Operator-permitted action; no role surface changes. |

**Result**: PASS, no violations. Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/005-schedule-recurrence-types/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── http-api-delta.md # Phase 1 output — recurrence request/response contract
└── checklists/
    └── requirements.md   # spec quality checklist (already present)
```

### Source Code (repository root)

```text
src/asset_dashboard/
├── scheduling/
│   ├── engine.py         # EXTEND: compute_next_run_at (once + unit interval + month math);
│   │                     #         validate_recurrence (new); one-shot handling in tick()
│   └── routes.py         # EDIT: validate recurrence on create/update/from-run; reject past "once"
├── web/
│   ├── templating.py     # EDIT: register `humanize_recurrence` Jinja global (Ukrainian)
│   ├── i18n.py           # EDIT: new STRINGS keys (kinds, units, fields, validation, status)
│   └── templates/
│       └── schedules.html # REWRITE form: once-above-interval, day→hour(24h)→minute, unit dropdown;
│                          #   list shows humanized recurrence + "completed" status for fired once;
│                          #   per-row Edit affordance that pre-fills the form and submits to the
│                          #   existing PUT /api/schedules/{id} (US4 — no new backend route)
└── (no model/migration changes)

tests/
├── unit/
│   └── test_recurrence.py            # NEW: compute per unit, month overflow, once, validation
├── integration/
│   ├── test_us1_once_schedule.py     # NEW: create once → fires once → disabled, not re-fired
│   └── test_us2_interval_units.py    # NEW: create interval-by-unit → fires + reschedules
└── contract/
    └── test_schedule.py              # EXTEND: new recurrence shapes accepted; bad shapes → 422;
                                      #   legacy tool-task recurrence still valid (regression)
```

**Structure Decision**: Single existing project; changes are localized to the `scheduling/` package,
the `web/` presentation layer, and tests. No new packages, no new top-level directories.

## Complexity Tracking

No constitution violations — section intentionally empty.

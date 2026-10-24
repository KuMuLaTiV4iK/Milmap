---
description: "Task list for feature 005 вЂ” one-time & unit-based interval schedules"
---

# Tasks: One-Time & Unit-Based Interval Schedules

**Input**: Design documents from `specs/005-schedule-recurrence-types/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/http-api-delta.md, quickstart.md

**Tests**: INCLUDED вЂ” required by Constitution Principle V (Testable) and spec SC-006.

**Organization**: Tasks are grouped by user story. US1 (once) and US2 (interval units) are
API-testable independently; US3 delivers the browser form that exposes both; US4 adds editing an
existing schedule from the list.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 / US2 / US3 (Setup, Foundational, Polish carry no story label)
- **Note on `engine.py`**: several tasks edit `src/asset_dashboard/scheduling/engine.py` (different
  branches of the same functions). They are **sequential** with one another вЂ” never marked `[P]`
  against each other вЂ” to avoid edit conflicts.

---

## Phase 1: Setup

**Purpose**: Confirm the baseline before changing shared scheduling code.

- [X] T001 Confirm the baseline: no new runtime dependency is needed, and the DB is at Alembic head (`alembic current` equals head). Record that this feature adds **no migration** (recurrence is JSON; once-completion reuses `enabled`/`last_triggered_at`).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared scaffolding in the engine, routes, and presentation layer that every story builds
on. **вљ пёЏ No story work can begin until this phase is complete.**

- [X] T002 Add `add_months(dt, n)` (advance calendar months, clamp day to the target month's last valid day вЂ” e.g. Jan 31 + 1 в†’ Feb 28/29) and `is_one_shot(recurrence)` (`type == "once"`) helpers in `src/asset_dashboard/scheduling/engine.py`
- [X] T003 Add `validate_recurrence(recurrence, *, now)` dispatcher in `src/asset_dashboard/scheduling/engine.py`: dispatch by `type`; keep legacy `interval{seconds}`, `daily`, `weekly` valid; unknown `type` в†’ `UnsupportedRecurrenceError`. (once and interval-unit branches are filled in US1/US2.)
- [X] T004 Wire `validate_recurrence(body.recurrence, now=utcnow())` into `api_create_schedule`, `api_update_schedule`, and `api_schedule_from_run` in `src/asset_dashboard/scheduling/routes.py`, returning the existing `validation_error({"recurrence": <msg>})` (HTTP 422) on failure вЂ” replacing the broad `try/except` around `compute_next_run_at`
- [X] T005 Register a `humanize_recurrence(recurrence)` Jinja global in `src/asset_dashboard/web/templating.py` with a legacy/fallback Ukrainian rendering (per-kind text for once/interval added in US1/US2)

**Checkpoint**: Engine dispatch, route validation, and the display helper exist (legacy shapes still work); stories can begin.

---

## Phase 3: User Story 1 вЂ” One-time ("once") schedule (Priority: P1) рџЋЇ MVP

**Goal**: An operator can schedule a scan to run exactly once at a chosen date/time; it fires once,
then is marked completed and never runs again.

**Independent Test**: via API/engine вЂ” create a `once` schedule for a near-future time, force it due,
`tick()` once в†’ exactly one run and the schedule becomes `enabled=false`; a second `tick()` does
nothing; a past `run_at` is rejected with 422.

### Tests for User Story 1

- [X] T006 [P] [US1] Unit tests for `once` in `tests/unit/test_recurrence.py`: `compute_next_run_at` returns the parsed `run_at`; `validate_recurrence` rejects missing/unparseable/past `run_at` and accepts a future one; `is_one_shot` is true for `once`
- [X] T007 [P] [US1] Integration test in `tests/integration/test_us1_once_schedule.py`: `POST /api/profiles/{id}/schedules` with a future `once` в†’ 201; force `next_run_at` due + `tick()` в†’ exactly one run, `enabled=False`, `last_triggered_at` set; second `tick()` в†’ no new run; past `run_at` в†’ 422

### Implementation for User Story 1

- [X] T008 [US1] Extend `compute_next_run_at` in `src/asset_dashboard/scheduling/engine.py`: `once` в†’ return the parsed `run_at` (naive-UTC ISO-8601)
- [X] T009 [US1] Extend `validate_recurrence` in `src/asset_dashboard/scheduling/engine.py`: `once` в†’ `run_at` present, parseable, and **strictly after `now`** (message e.g. "run_at must be in the future")
- [X] T010 [US1] One-shot handling in `tick()` in `src/asset_dashboard/scheduling/engine.py`: after a `once` schedule fires, set `enabled=False` + `last_triggered_at=now` and **do not** recompute `next_run_at`; guard the overlap branch (SKIP в†’ disable; QUEUE в†’ leave enabled to retry) and the severely-overdue catch-up branch (RUN_ONCE в†’ fire then disable; SKIP в†’ disable) so a once schedule can never loop or re-fire
- [X] T011 [P] [US1] Add the `once` branch to `humanize_recurrence` in `src/asset_dashboard/web/templating.py` (e.g. `РћРґРЅРѕСЂР°Р·РѕРІРѕ: 2026-10-25 23:00`) and a completed-state derivation (`once` AND not `enabled` AND `last_triggered_at`)
- [X] T012 [P] [US1] Add `once` i18n keys in `src/asset_dashboard/web/i18n.py`: kind label `РћРґРЅРѕСЂР°Р·РѕРІРѕ`, completed marker `Р’РёРєРѕРЅР°РЅРѕ`, once field labels (РґРµРЅСЊ / РіРѕРґРёРЅР° / С…РІРёР»РёРЅР°), and the past-time validation message

**Checkpoint**: One-time schedules work end-to-end at the API/engine level and are testable independently.

---

## Phase 4: User Story 2 вЂ” Recurring interval by unit (Priority: P2)

**Goal**: An operator can schedule a recurring scan as "every N Г— unit" (minute/hour/day/week/month)
with no absolute clock time.

**Independent Test**: via API/engine вЂ” create an interval `{every:2, unit:"hour"}` в†’ `next_run_at в‰€
now + 2h`; force due + `tick()` в†’ a run and `next_run_at` advances one interval; invalid `every`/`unit`
в†’ 422; month arithmetic clamps correctly.

### Tests for User Story 2

- [X] T013 [P] [US2] Unit tests for interval units in `tests/unit/test_recurrence.py`: `compute_next_run_at` for minute/hour/day/week; `month` via `add_months` including `2026-01-31 + 1 month в†’ 2026-02-28`; `validate_recurrence` rejects `every < 1` / non-integer and a bad `unit`, and accepts all five units
- [X] T014 [P] [US2] Integration test in `tests/integration/test_us2_interval_units.py`: `POST вЂ¦/schedules` with `{type:"interval", every:2, unit:"hour"}` в†’ 201 and `next_run_at в‰€ +2h`; force due + `tick()` в†’ a run and `next_run_at` advanced; `every:0` and `unit:"fortnight"` в†’ 422

### Implementation for User Story 2

- [X] T015 [US2] Extend `compute_next_run_at` in `src/asset_dashboard/scheduling/engine.py`: interval-unit minute/hour/day/week via `timedelta` (week = 7 days) and month via `add_months`
- [X] T016 [US2] Extend `validate_recurrence` in `src/asset_dashboard/scheduling/engine.py`: interval-unit `every` is an integer в‰Ґ 1 and `unit в€€ {minute, hour, day, week, month}` (messages per contract)
- [X] T017 [P] [US2] Add the interval branch to `humanize_recurrence` in `src/asset_dashboard/web/templating.py` (e.g. `РљРѕР¶РЅС– 2 РіРѕРґ`) with correct Ukrainian unit wording
- [X] T018 [P] [US2] Add interval i18n keys in `src/asset_dashboard/web/i18n.py`: kind label `Р†РЅС‚РµСЂРІР°Р»`, unit names `С…РІРёР»РёРЅР° / РіРѕРґРёРЅР° / РґРµРЅСЊ / С‚РёР¶РґРµРЅСЊ / РјС–СЃСЏС†СЊ`, the count-field label, and interval validation messages

**Checkpoint**: Both once and interval-by-unit schedules work and are independently testable.

---

## Phase 5: User Story 3 вЂ” Clear, Ukrainian, correctly ordered form (Priority: P3)

**Goal**: The `/schedules` create form is readable and localized: once above interval; once inputs
ordered day в†’ hour (24h) в†’ minute; interval as a number + Ukrainian unit dropdown; inline validation;
and the list shows a humanized, localized recurrence.

**Independent Test**: open `/schedules` вЂ” the kind dropdown lists `РћРґРЅРѕСЂР°Р·РѕРІРѕ` above `Р†РЅС‚РµСЂРІР°Р»`; once
shows dayв†’hourв†’minute; interval shows a number + the 5 Ukrainian units; an invalid save shows inline;
the list renders humanized recurrence.

### Tests for User Story 3

- [X] T019 [P] [US3] Integration/template test in `tests/integration/test_us3_schedule_form.py`: `GET /schedules` в†’ 200; `РћРґРЅРѕСЂР°Р·РѕРІРѕ` option appears before `Р†РЅС‚РµСЂРІР°Р»`; the unit dropdown contains the five Ukrainian units; a humanized recurrence (not a raw dict) is rendered in the list

### Implementation for User Story 3

- [X] T020 [US3] Rewrite the create form in `src/asset_dashboard/web/templates/schedules.html`: recurrence-kind `<select>` with `РћРґРЅРѕСЂР°Р·РѕРІРѕ` first and `Р†РЅС‚РµСЂРІР°Р»` second; a once field group (date picker в†’ hour 0вЂ“23 в†’ minute 0вЂ“59, in that order); an interval group (whole-number input + unit `<select>` of the five units); remove the obsolete `daily`/`interval-seconds` inputs; show only the selected group via JS
- [X] T021 [US3] Update the form JavaScript in `src/asset_dashboard/web/templates/schedules.html`: build a `once` recurrence by converting the picked local day/hour/minute to a UTC ISO `run_at`; build `{type:"interval", every, unit}`; POST; on a 422 show `error.fields.recurrence`/`error.message` inline in `#schedule-error` (no `alert`, no reload-on-error)
- [X] T022 [US3] Replace the raw `{{ s.recurrence }}` list cell in `src/asset_dashboard/web/templates/schedules.html` with `humanize_recurrence(s.recurrence)` and a completed marker for a fired once schedule

**Checkpoint**: The scheduling create form is fully usable and localized in the browser.

---

## Phase 6: User Story 4 вЂ” Edit an existing schedule (Priority: P3)

**Goal**: An operator can edit any schedule in the list (recurrence, target, label, enabled) and save
it in place, reusing the same form controls вЂ” no delete-and-recreate. Uses the existing
`PUT /api/schedules/{id}` endpoint; **no new backend route**.

**Independent Test**: edit a saved schedule вЂ” change its recurrence (e.g. interval в†’ once), target,
label, and enabled вЂ” save; the row updates in place with a recomputed next run and an audit entry; an
invalid edit (past once / bad interval) is rejected inline and leaves the schedule unchanged; a
completed once re-enabled with a future time becomes active again.

### Tests for User Story 4

- [X] T023 [P] [US4] Integration test in `tests/integration/test_us4_edit_schedule.py`: `PUT /api/schedules/{id}` changing recurrence (interval в†’ once), target, label, and enabled в†’ schedule updated in place (same id), `next_run_at` recomputed, a `SCHEDULE_CHANGE` audit event recorded; an invalid edit (past `once`) в†’ 422 and the schedule unchanged; re-enabling a completed once with a future `run_at` в†’ `enabled=True` and the new `next_run_at`

### Implementation for User Story 4

- [X] T024 [US4] Add a per-row **Edit** button in `src/asset_dashboard/web/templates/schedules.html` that carries the schedule's current values (recurrence kind/fields, target, label, enabled) and loads them into the form in "edit mode" (e.g. via `data-*` attributes / a JS lookup)
- [X] T025 [US4] Extend the form JavaScript in `src/asset_dashboard/web/templates/schedules.html` for edit mode: pre-fill the kind, once/interval fields, target, label, and enabled from the selected row; submit to `PUT /api/schedules/{id}`; on success update the row in place (and reset back to create mode); on 422 show the error inline; add i18n keys in `src/asset_dashboard/web/i18n.py` for Edit / Save changes / Cancel

**Checkpoint**: Schedules can be created, edited, and deleted entirely from the browser.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T026 [P] Backward-compatibility regression test in `tests/contract/test_schedule.py`: a legacy `interval{seconds}` and a `daily` recurrence still pass `validate_recurrence` and compute a next run, and a `ToolTask` with a legacy recurrence still fires via `tick()` (FR-014 / SC-005)
- [X] T027 [P] Update the scheduling capability bullet in `README.md` (one-time + unit-based interval schedules; create/edit/delete from the UI; note `daily`/`weekly` removed from the discovery-schedule UI, still understood by the engine)
- [X] T028 Run `python -m pytest tests/ -q` (all green вЂ” no 001/002/003 regressions, SC-006) and `ruff check src tests` (clean)
- [X] T029 Execute `quickstart.md` scenarios 1вЂ“6 plus an edit check against a throwaway runtime DB (never `data/app.sqlite3`)

---

## Dependencies & Execution Order

- **Setup (T001)** в†’ **Foundational (T002вЂ“T005)** в†’ **all user stories**.
- **US1 (T006вЂ“T012)**, **US2 (T013вЂ“T018)**: both depend only on Foundational. They can proceed in
  priority order; their `engine.py` tasks (T008вЂ“T010, T015вЂ“T016) are **sequential** because they edit
  the same file/functions. Their `[P]` test, templating, and i18n tasks run in parallel.
- **US3 (T019вЂ“T022)** depends on Foundational and is best done after US1/US2 so `humanize_recurrence`
  has both branches (T011, T017); all three US3 implementation tasks edit `schedules.html` and are
  therefore sequential with each other.
- **US4 (T023вЂ“T025)** depends on Foundational + US3 (it reuses the create form and its JS); its two
  implementation tasks (T024, T025) edit `schedules.html` and are sequential with the US3 form tasks.
  No new backend вЂ” it uses the existing `PUT /api/schedules/{id}`.
- **Polish (T026вЂ“T029)** after the stories it validates. T028/T029 run last.

### Parallel opportunities

- Within US1: `T006`, `T007` (tests) в€Ґ each other; then `T011`, `T012` (different files) в€Ґ each other.
- Within US2: `T013`, `T014` в€Ґ; then `T017`, `T018` в€Ґ.
- Polish: `T026`, `T027` в€Ґ.

### Parallel example (US1)

```text
# tests first (different files):
T006  tests/unit/test_recurrence.py (once portions)
T007  tests/integration/test_us1_once_schedule.py
# then presentation bits (different files):
T011  web/templating.py (once humanize)
T012  web/i18n.py (once strings)
# engine edits T008 в†’ T009 в†’ T010 remain sequential (same file)
```

---

## Implementation Strategy

### MVP (User Story 1)

1. T001 в†’ T002вЂ“T005 (foundation) в†’ T006вЂ“T012 (once).
2. **STOP & VALIDATE**: once schedules fire exactly once via the engine/API and past times are
   rejected. (US3 then makes once/interval usable in the browser.)

### Incremental delivery

Foundation в†’ US1 (once, API) в†’ US2 (interval units, API) в†’ US3 (localized browser form) в†’
US4 (edit from the list) в†’ Polish. Each story is an independently testable increment; backward
compatibility for the shared credential-tool scheduler is protected by T026.

---

## Notes

- No database migration вЂ” `recurrence` is JSON; once-completion reuses `enabled`/`last_triggered_at`.
- No new runtime dependency вЂ” month arithmetic uses the standard library.
- Keep legacy recurrence shapes valid in the engine (credential-tool tasks share it).
- Commit after each task or logical group; verify new tests fail before implementing.

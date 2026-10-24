# Quickstart / Validation — Feature 005 (schedule recurrence types)

Validates the once + unit-based-interval schedule behavior end to end. Run against an isolated test
DB or a throwaway runtime DB — **never** the real `data/app.sqlite3`.

## Prerequisites

- Dependencies installed (no new ones for this feature).
- Schema current (`alembic upgrade head`) — this feature adds no migration, but the DB must already
  be at head from feature 003/004.
- An operator account to sign in with.

## Automated checks (primary)

```powershell
# Full suite must stay green (SC-006)
python -m pytest tests/ -q

# Feature-focused
python -m pytest tests/unit/test_recurrence.py tests/integration/test_us1_once_schedule.py `
                 tests/integration/test_us2_interval_units.py tests/contract/test_schedule.py -q

ruff check src tests
```

Expected: all pass; no regressions in features 001/002/003.

## Scenario 1 — One-time schedule fires exactly once (US1 / SC-001)

1. Create a target-less or normal profile.
2. `POST /api/profiles/{id}/schedules` with
   `{"recurrence": {"type": "once", "run_at": "<~1 min in the future, UTC>"}, "target_scope": ["127.0.0.1"]}`
   → **201**, schedule `enabled=true`, `next_run_at == run_at`.
3. Drive the engine: set `next_run_at` to now and call `tick(session)` (as the integration tests do),
   or wait for the heartbeat.
   - Expected: the run starts (**1** run id returned), `last_triggered_at` set.
4. Call `tick(session)` again.
   - Expected: **no** new run; the schedule is now `enabled=false` ("Виконано" in the list).

## Scenario 2 — Past "once" time is rejected (US1 / SC-004)

- `POST …/schedules` with `run_at` in the past → **422**, `fields.recurrence` set, no schedule created.

## Scenario 3 — Interval by unit fires and repeats (US2 / SC-002)

1. `POST …/schedules` with `{"recurrence": {"type": "interval", "every": 2, "unit": "hour"}, ...}`
   → **201**, `next_run_at ≈ now + 2h`.
2. Force-due + `tick` → run starts; `next_run_at` advances ~2h beyond the fire time (keeps recurring).
3. Check month math unit-side: `compute_next_run_at({type:interval,every:1,unit:month}, 2026-01-31)`
   → `2026-02-28` (no crash, clamped).

## Scenario 4 — Invalid interval rejected (US2 / SC-004)

- `every: 0` or `unit: "fortnight"` → **422**, `fields.recurrence` set.

## Scenario 5 — Form UX & Ukrainian (US3 / SC-003)

Open `/schedules` in a local browser and confirm:
- The recurrence-kind dropdown lists **Одноразово** above **Інтервал**.
- Selecting *once* shows date → hour (0–23) → minute, in that order; selecting *interval* shows a
  number + a unit dropdown with **хвилина / година / день / тиждень / місяць**.
- An invalid submission shows the error inline (no browser `alert`, no 500 page).
- The list renders a humanized recurrence (e.g., `Кожні 2 год`, `Одноразово: …`) and marks a fired
  once schedule as completed.

## Scenario 6 — Credential-tool tasks unaffected (FR-014 / SC-005)

- Run the existing credential-tool scheduling tests; a legacy `interval{seconds}` / `daily`
  recurrence still computes a next run and fires via the shared `tick()`.

## Scenario 7 — Edit an existing schedule (US4 / SC-007)

1. Create any schedule, then on `/schedules` choose **Edit** on its row → the form pre-fills with that
   schedule's recurrence kind/values, target, label, and enabled state.
2. Change it (e.g. interval → once, or adjust the target/label/enabled) and save →
   `PUT /api/schedules/{id}` updates the **same** schedule in place, the row reflects the change, and
   `next_run_at` is recomputed; a `SCHEDULE_CHANGE` audit event is recorded.
3. Submit an invalid edit (past `once` time) → **422** inline; the schedule is unchanged.
4. Edit a completed one-time schedule to a future time and enable it → it becomes active again.

## Done when

- Scenarios 1–6 pass, the full pytest suite is green, and `ruff check src tests` is clean.

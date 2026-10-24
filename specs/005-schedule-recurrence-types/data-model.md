# Phase 1 Data Model: One-Time & Unit-Based Interval Schedules

**No database migration.** This feature changes only the *shape of the JSON* stored in the existing
`Schedule.recurrence` column and the *interpretation* of existing state fields. The `Schedule` table
structure (and `ToolTask`, which shares the engine) is unchanged.

## Entity: Schedule (existing — fields relevant here)

| Field | Type | Role in this feature |
|-------|------|----------------------|
| `recurrence` | JSON | Holds the recurrence shape (see below). Changed shapes, same column. |
| `next_run_at` | datetime (naive UTC) | Seeded from `compute_next_run_at(recurrence, now)` on create/update. For `once`, equals `run_at`. |
| `enabled` | bool | For a `once` schedule, set to `False` after it fires (completion marker). |
| `last_triggered_at` | datetime \| null | Set to the fire time; combined with `enabled=False` and `type==once` ⇒ "completed". |
| `target_scope`, `label`, `overlap_policy`, `catch_up_policy` | — | Unchanged; preserved behavior (FR-013). |

## Value object: recurrence (JSON shapes)

### once (new)
```json
{ "type": "once", "run_at": "2026-10-25T23:00:00" }
```
- `run_at`: ISO-8601, naive UTC (browser converts the operator's local day/hour/minute). Validation:
  present, parseable, **strictly after `now`** at create/update time.
- Non-repeating (one-shot).

### interval — unit form (new)
```json
{ "type": "interval", "every": 2, "unit": "hour" }
```
- `every`: integer ≥ 1. `unit` ∈ `{minute, hour, day, week, month}`. Repeating.

### Legacy shapes (still valid in the engine, not emitted by the discovery UI)
```json
{ "type": "interval", "seconds": 86400 }
{ "type": "daily",  "hour": 2, "minute": 0 }
{ "type": "weekly", "hour": 2, "minute": 0, "day_of_week": 0 }
```

## Validation rules (`validate_recurrence(recurrence, *, now)`)

| Kind | Rule | On failure |
|------|------|-----------|
| once | `run_at` present & parseable | 422 `{recurrence: "…"}` |
| once | `run_at` strictly in the future | 422 `{recurrence: "…"}` (FR-005) |
| interval (unit) | `every` is an integer ≥ 1 | 422 (FR-010) |
| interval (unit) | `unit` in allowed set | 422 |
| interval (legacy) | `seconds` is an integer ≥ 1 | 422 |
| daily/weekly | hour 0–23, minute 0–59, day_of_week 0–6 | 422 |
| any | unknown `type` | 422 |

Validation is applied by all three creating routes: `POST /api/profiles/{id}/schedules`,
`PUT /api/schedules/{id}`, `POST /api/runs/{id}/schedule`.

## State transitions

### once schedule
```
created (enabled=true, next_run_at=run_at, last_triggered_at=null)
   │  heartbeat reaches run_at
   ▼
fired once  → enabled=false, last_triggered_at=now   ["Виконано" / completed]
   │  subsequent heartbeats
   ▼
never fires again (enabled=false ⇒ not selected by tick)
```
Edge branches (one-shot, from research D2):
- overlap SKIP → disable without a second attempt; overlap QUEUE → remain enabled, retry next tick.
- catch-up when severely overdue: RUN_ONCE → fire then disable; SKIP → disable without firing.
- past `run_at` at creation → rejected (never created).

### interval schedule (unchanged lifecycle, new cadence source)
```
created (enabled=true, next_run_at=now+interval)
   │ heartbeat reaches next_run_at
   ▼
fired → last_triggered_at=now, next_run_at=compute_next_run_at(recurrence, now)   (repeats)
```

## Computation: `compute_next_run_at(recurrence, after)`

- once → return parsed `run_at`.
- interval unit minute/hour/day/week → `after + N·unit` (week = 7 days).
- interval unit month → `add_months(after, N)` with end-of-month clamping (research D3).
- interval legacy seconds / daily / weekly → unchanged existing behavior.
- unknown → raise `UnsupportedRecurrenceError`.

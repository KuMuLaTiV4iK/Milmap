# Phase 0 Research: One-Time & Unit-Based Interval Schedules

All decisions below resolve the design questions raised by the spec. No `NEEDS CLARIFICATION`
remained in the Technical Context; the two spec-level defaults (removing fixed-clock "daily";
local-time "once") are recorded here as decisions.

## D1 — Recurrence JSON shapes

**Decision**: Extend the JSON stored in `Schedule.recurrence` with two new shapes and keep the
existing ones valid:

| Kind | Shape | Repeats? |
|------|-------|----------|
| once (new) | `{"type": "once", "run_at": "<ISO-8601 UTC, naive>"}` | No (one-shot) |
| interval (new form) | `{"type": "interval", "every": <int ≥ 1>, "unit": "minute\|hour\|day\|week\|month"}` | Yes |
| interval (legacy) | `{"type": "interval", "seconds": <int ≥ 1>}` | Yes |
| daily (legacy) | `{"type": "daily", "hour": h, "minute": m}` | Yes |
| weekly (legacy) | `{"type": "weekly", "hour": h, "minute": m, "day_of_week": d}` | Yes |

**Rationale**: `recurrence` is already a schema-less JSON column, so new shapes need no migration.
The discovery-schedule UI will only ever *emit* the two new shapes; the legacy shapes stay readable
so existing `ToolTask` rows and any stored recurrence keep computing (FR-014).

**Alternatives considered**: (a) a dedicated `recurrence_unit`/`run_at` column set — rejected, needs
a migration for no benefit; (b) dropping legacy shapes — rejected, would break the shared
credential-tool scheduler.

## D2 — One-shot ("once") lifecycle

**Decision**: `compute_next_run_at` returns the parsed `run_at` for a `once` recurrence (used at
create/update to seed `next_run_at`). In `tick()`, a `once` schedule is treated as **one-shot**:
after it fires, set `enabled = False` and `last_triggered_at = now`, and **do not** recompute
`next_run_at`. A small predicate `is_one_shot(recurrence)` (`type == "once"`) gates this.

The one-shot branch also covers the non-happy paths so they can never loop:
- **Overlap (a run already in progress)**: `SKIP` → disable the once schedule (its moment passed);
  `QUEUE` → leave `enabled=True`/`next_run_at` so the next tick retries once the run frees up.
- **Catch-up when severely overdue**: the existing `while next_at <= now: compute_next_run_at(...)`
  loop MUST be skipped for one-shot (it would never advance). Instead, honor the policy: `RUN_ONCE`
  → fire now then disable; `SKIP` → disable without firing.

**Rationale**: Reusing `enabled=False` + `last_triggered_at` means no new state column; "completed"
is derivable in the UI as *once-type AND not enabled AND last_triggered_at set*.

**Alternatives considered**: a new `status`/`completed_at` column — rejected (migration, redundant
with existing fields).

## D3 — Interval unit arithmetic (incl. month)

**Decision**: Compute the next run from `after`:
- minute/hour/day/week → `after + timedelta(...)` (`week` = 7 days).
- month → add `every` **calendar months** with a stdlib helper `add_months(dt, n)`: advance
  year/month arithmetically, then clamp the day to the last valid day of the target month
  (e.g., Jan 31 + 1 month → Feb 28/29). No `dateutil` dependency.

**Rationale**: Honors "every N months on the same day/time" intuitively, handles short months
without crashing or stalling (FR-009), and adds no dependency (Principle I).

**Alternatives considered**: approximating a month as 30 days — rejected, drifts across the calendar
and surprises operators; `dateutil.relativedelta` — rejected, new dependency.

## D4 — Time zone for "once"

**Decision**: The browser (which knows the host's local time) converts the operator's picked
day/hour/minute into an **absolute instant and sends it as a naive UTC ISO-8601 string** in
`run_at`. The server stores it as-is and compares against `utcnow()` (the engine's existing
naive-UTC basis). For display, timestamps are rendered the same way the page already renders
`next_run_at`/`last_triggered_at`.

**Rationale**: Browser and server share the same host and therefore the same local time zone, so the
browser is the correct, dependency-free place to resolve local→UTC. This keeps the engine on its
existing naive-UTC comparisons and avoids introducing a server-side time-zone database.

**Alternatives considered**: server-side local-tz conversion — rejected, needs host-tz handling and
duplicates what the browser already knows; storing local naive time — rejected, would mismatch the
engine's `utcnow()` comparisons and mis-fire.

**Note (out of scope)**: the legacy `daily`/`weekly` shapes compute against `utcnow()` and so fire at
a UTC clock time — a pre-existing quirk. Since `daily`/`weekly` are being removed from the
discovery-schedule UI (D6), this feature does not change that behavior for the tool tasks that may
still use them.

## D5 — Create-form UI and validation

**Decision**:
- Recurrence-kind `<select>` lists **once first, interval second**, labeled in Ukrainian.
- **once** group: a native date picker (`<input type="date">`) + an hour input (0–23) + a minute
  input (0–59), in that order. JS composes local date+hour+minute → UTC ISO `run_at`.
- **interval** group: a whole-number input + a unit `<select>` with the five Ukrainian units.
- JS shows only the group for the selected kind and builds the matching recurrence JSON.
- **Validation** is server-authoritative via a new `validate_recurrence(recurrence, *, now)` used by
  all three schedule-creating routes: once → `run_at` present/parseable **and strictly in the
  future**; interval → `every` a positive integer and `unit` in the allowed set (legacy shapes still
  accepted). Errors return the existing `422` validation-error shape and are shown inline on the form
  (FR-012). Client-side `min`/`required` attributes are a convenience only.

**Rationale**: Mirrors the existing form/validation pattern (`validation_error`, inline
`#schedule-error`), so it stays consistent and testable.

## D6 — Removing daily/weekly from the discovery-schedule UI

**Decision**: The discovery-schedule form offers only **once** and **interval**. "daily
(hour:minute)" and the never-exposed "weekly" are removed from that form. The engine still
*understands* them for backward compatibility (D1). There are currently **0** stored schedules, so
there is nothing to migrate.

**Rationale**: Directly implements the operator's request; fixed-clock daily recurrence is
approximated by "every 1 day" (recurs 24h after each run). Flagged in the spec Assumptions for the
operator to override if fixed-clock daily is actually required.

## D7 — Ukrainian display of recurrence

**Decision**: Add a `humanize_recurrence(recurrence)` helper registered as a Jinja global (like the
existing `port_row_view`), rendering e.g. `Одноразово: 2026-10-25 23:00`, `Кожні 2 год`, `Щодня`
(every 1 day), etc., replacing the raw `{{ s.recurrence }}` dict in the list. The list also shows a
"Виконано" (completed) marker for a fired once schedule.

**Rationale**: FR-011 (Ukrainian) and US3 (readable form/list); keeping it a presentation helper
avoids leaking display concerns into the engine.

## Summary of decisions

- Two new JSON recurrence shapes; legacy shapes retained (no migration). [D1]
- `once` is one-shot: fire then disable, reusing existing fields; guarded in every `tick` branch. [D2]
- Unit arithmetic incl. calendar-correct months via a stdlib helper. [D3]
- Browser resolves local→UTC for `once`; engine stays naive-UTC. [D4]
- Server-authoritative `validate_recurrence`; inline errors; once-first form with day→hour→minute and
  a Ukrainian unit dropdown. [D5]
- daily/weekly removed from the discovery UI, kept valid in the engine. [D6]
- Ukrainian recurrence humanizer for the list. [D7]

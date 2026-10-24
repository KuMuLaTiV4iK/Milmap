# HTTP API Delta — Feature 005 (schedule recurrence types)

This feature changes **no routes, paths, methods, or status codes**. The existing schedule endpoints
(feature 003) keep their shapes; only the accepted/returned `recurrence` object gains two new forms
and gains server-side validation. Listed here for the contract record.

## Affected endpoints (unchanged signatures)

| Method | Path | Change |
|--------|------|--------|
| POST | `/api/profiles/{profile_id}/schedules` | `recurrence` accepts `once` and interval-unit shapes; validated. |
| PUT | `/api/schedules/{schedule_id}` | same recurrence validation. |
| POST | `/api/runs/{run_id}/schedule` | same recurrence validation (create-from-history). |
| GET | `/api/profiles/{profile_id}/schedules` | response `recurrence` may now be a `once` or interval-unit object. |
| DELETE | `/api/schedules/{schedule_id}` | unchanged. |
| GET | `/schedules` (page) | form redesigned; list shows humanized recurrence + completion status. |

## Request body — `recurrence` field

Create/update bodies are unchanged except for the `recurrence` object. Accepted shapes:

```jsonc
// one-time
{ "recurrence": { "type": "once", "run_at": "2026-10-25T23:00:00" } }

// recurring, unit-based
{ "recurrence": { "type": "interval", "every": 2, "unit": "hour" } }
//   unit ∈ "minute" | "hour" | "day" | "week" | "month";  every ≥ 1
```

Legacy shapes (`interval{seconds}`, `daily`, `weekly`) remain accepted for backward compatibility but
are not emitted by the discovery-schedule UI.

Full create body (unchanged around `recurrence`):

```jsonc
{
  "recurrence": { "type": "once", "run_at": "2026-10-25T23:00:00" },
  "target_scope": ["192.168.1.3"],   // optional; defaults to the profile's target
  "label": "One-off audit",          // optional
  "enabled": true,                     // optional
  "overlap_policy": "skip",           // optional: skip | queue
  "catch_up_policy": "run_once"       // optional: run_once | skip
}
```

## Validation errors

All validation failures use the existing error envelope and HTTP **422**:

```jsonc
// past "once" time
{ "error": { "code": "validation_error", "message": "...", "fields": { "recurrence": "run_at must be in the future" } } }

// bad interval
{ "error": { "code": "validation_error", "message": "...", "fields": { "recurrence": "every must be a positive whole number" } } }

// bad unit
{ "error": { "code": "validation_error", "message": "...", "fields": { "recurrence": "unit must be one of minute, hour, day, week, month" } } }
```

(Exact messages are implementation-defined; the field key is `recurrence`.)

## Response body — `recurrence` field

`GET` responses echo the stored recurrence object verbatim, e.g.:

```jsonc
{
  "id": "…", "profile_id": "…",
  "recurrence": { "type": "once", "run_at": "2026-10-25T23:00:00" },
  "target_scope": ["192.168.1.3"], "label": "One-off audit",
  "enabled": false,                       // false + once + last_triggered_at ⇒ completed
  "next_run_at": "2026-10-25T23:00:00",
  "overlap_policy": "skip", "catch_up_policy": "run_once",
  "last_triggered_at": "2026-10-25T23:00:12"
}
```

## Backward-compatibility contract (FR-014)

The standalone credential-tool task scheduler (`ToolTask`) shares `compute_next_run_at`. Any
recurrence shape it already stores MUST continue to compute. A regression test asserts a legacy
`interval{seconds}` (and a `daily`) recurrence still produces a valid next run.

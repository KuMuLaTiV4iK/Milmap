# HTTP API Delta — Feature 003

New and changed endpoints vs features 001/002. All endpoints require an
authenticated session (Principle II). Error bodies use the existing
`api_error(code, message)` / `validation_error(fields)` shapes.

## US1 — Home page & target-less launch

### Changed: `POST /api/profiles/{profile_id}/runs`

Start (or cache-serve) a run. Body gains an optional target override.

```jsonc
// request
{
  "force_fresh": false,
  "target_scope": ["10.0.0.0/24"]   // NEW, optional. Required (effective) when the
                                     // profile has no saved target. Only the target
                                     // is settable here — ports/params come from the profile.
}
```

Behavior:

- Effective target = `target_scope` if provided, else the profile's saved target.
- If the effective target is empty → `400 {"error":{"code":"target_required"}}`.
- A provided `target_scope` is validated like a profile target; invalid →
  `422 validation_error`.
- When `target_scope` is provided, the fresh-cache path is skipped (treated as
  `force_fresh`) so a cached run for a different target is never served.
- The override is used for this run only and is **not** persisted to the profile.
- Responses unchanged: `202 {run_id, status}`; `200 {..., served_from_cache}`;
  `409 already_running`; `503 concurrency_limit`.

### Changed: `POST /api/profiles` and `PUT /api/profiles/{id}`

- `target_scope` may be an **empty list** (target-less profile, FR-003a). A
  non-empty `target_scope` is still validated. All other fields unchanged.

### Changed: Home page `GET /`

- Renders the Home ("Головна") page: ≤5 recent profiles (by `updated_at`) each
  with a Run-now action, and ≤20 recent scans across all profiles with posture
  or "not applicable". No request/response contract for callers (server-rendered).

## US2 — Dynamic UI

### Changed: `POST /api/profiles/{id}/duplicate`, `DELETE /api/profiles/{id}`

- Behavior unchanged server-side; when requested with `HX-Request`, return an
  HTML fragment (the new `<tr>` for duplicate; empty body / `200` for delete) so
  the profiles list updates in place. JSON responses remain for API/tests.

## US4 — Reference-versions dictionary

Editable by Operators and Administrators (session auth; not admin-gated). Every
mutation records a `CONFIG_CHANGE` audit event.

| Method & Path | Purpose |
|---------------|---------|
| `GET /reference-versions` | Page: the maintained reference-version list (vendor, product, version_match, status, note). |
| `GET /api/reference-versions` | List entries (JSON). |
| `POST /api/reference-versions` | Create an entry → `201`. Body: `{vendor, product, version_match, status: "valid"|"invalid", note?}`. |
| `PUT /api/reference-versions/{id}` | Update an entry. |
| `DELETE /api/reference-versions/{id}` | Remove an entry → `204`. |

Validation: `status` ∈ {`valid`,`invalid`}; `vendor`/`product`/`version_match`
non-empty. Invalid → `422 validation_error`.

## US6 — Profile-scan schedules (own target, multiple, from history)

Replaces the single-schedule-per-profile endpoints with per-schedule CRUD.
Every mutation records a `SCHEDULE_CHANGE` audit event.

| Method & Path | Purpose |
|---------------|---------|
| `GET /api/profiles/{profile_id}/schedules` | List all schedules for a profile. |
| `POST /api/profiles/{profile_id}/schedules` | Create a schedule → `201`. |
| `PUT /api/schedules/{schedule_id}` | Update a schedule. |
| `DELETE /api/schedules/{schedule_id}` | Delete a schedule → `204`. |
| `POST /api/runs/{run_id}/schedule` | Create a schedule from a past run → `201`. |

Schedule body:

```jsonc
{
  "recurrence": {"type": "daily", "hour": 2, "minute": 0},  // existing recurrence shapes
  "target_scope": ["10.0.0.0/24"],   // REQUIRED, the schedule's own target (FR-021a)
  "label": "nightly /24 sweep",       // optional
  "enabled": true,
  "overlap_policy": "skip",
  "catch_up_policy": "run_once"
}
```

Behavior:

- `target_scope` is validated with `validate_target_scope`; empty/invalid →
  `422 validation_error` (FR-021b). On create, if omitted and the profile has a
  saved target, it defaults to the profile's target.
- `recurrence` validated by `compute_next_run_at` as today; invalid → `422`.
- `POST /api/runs/{run_id}/schedule`: copies the run's `profile_id` and
  `params_used.target_scope` onto the new schedule (body may still override
  `recurrence`/`label`); if the run's profile no longer exists → `404`.
- Every run a schedule fires is recorded in history and audit identically to a
  manual run (FR-022), honoring the no-duplicate-concurrent-run rule.

### Changed: `GET /schedules` page

- Lists schedules with their target and label; shows multiple rows per profile;
  offers create/edit. The Home, History, and run-results pages offer a "schedule
  this scan" action.

  > **Updated (feature 005):** the "schedule this scan" action no longer calls
  > `POST /api/runs/{run_id}/schedule` behind a seconds prompt. It now links to
  > `GET /schedules?from_run=<run_id>`, which pre-fills the create form with that
  > run's profile and scanned target (both still editable) and lets the operator
  > choose a recurrence before saving via `POST /api/profiles/{id}/schedules`.
  > The `POST /api/runs/{run_id}/schedule` endpoint remains available as an API.

## Unchanged results contract (US3 is render-only)

- `GET /api/runs/{id}/results` and `GET /api/history/{id}` still return
  `open_ports` per asset; each port entry now includes `state`. Small-vs-large
  presentation is applied by the server-rendered views, not by API filtering, so
  API consumers see the full per-port truth.

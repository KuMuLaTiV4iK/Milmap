# HTTP API Delta: Credential-Check Tool Fixes

All routes are under the existing credential-tool prefix
`/api/tools/credential-check` and require an authenticated Operator session
(CSRF token on mutating calls), unchanged from feature 002/007. Only additions
and changed shapes are listed.

## Conventions

- Error envelope unchanged: `{ "error": { "code", "message", "fields"? } }`;
  validation failures return `422` with per-field messages.
- Timestamps are ISO-8601; `once` recurrence `run_at` is an absolute UTC instant.

---

## 1. Run now (changed) — `POST /api/tools/credential-check`

Starts a check **asynchronously** (FR-112): returns immediately with the run in
`running` status.

Request (added `dictionary_id`, optional `attempt_ceiling`):

```jsonc
{
  "target_scope": ["10.10.0.5", "10.10.0.6"],
  "port": 443,
  "service": "https",
  "dictionary_id": "<DefaultCredentialEntry id>",   // required when ≥1 dict exists for service
  "attempt_ceiling": null                             // optional; null ⇒ dictionary size
}
```

Response `201`:

```json
{ "run_id": "<id>", "status": "running" }
```

- `422` if `target_scope` empty, `service` unknown, or no dictionary exists for
  the service (message guides the operator to create one — FR-104 / US2 #4).
- The run row exists in history with `status:"running"` before probing begins.

## 2. Dictionaries for a service (changed) — `GET /api/tools/credential-check/credentials`

Adds an optional `service` filter for the form selector (3.2):

`GET /api/tools/credential-check/credentials?service=https`

Response `200` (each item gains `probe_config`):

```jsonc
[
  {
    "id": "<id>",
    "vendor": "Generic web UI (HTTPS)",
    "service": "https",
    "credentials": [{ "username": "admin", "secret": "admin" }],
    "success_keywords": ["Dashboard", "Logout"],
    "probe_config": { "login_path": "/login", "method": "POST", "...": "..." }
  }
]
```

## 3. Dictionary create/update (changed) — `POST` / `PUT /.../credentials[/{id}]`

Request body gains optional `probe_config` (see data-model.md for the full
shape); omitted ⇒ `{}` ⇒ probe defaults:

```jsonc
{
  "service": "http",
  "vendor": "Acme routers",
  "credentials": [{ "username": "admin", "secret": "admin" }],
  "success_keywords": ["Welcome"],
  "probe_config": {
    "login_path": "/login",
    "username_field": "user",
    "password_field": "pass",
    "success": { "status": [200, 302] },
    "failure": { "status": [401] }
  }
}
```

Validation: `method ∈ {GET, POST}`, `encoding ∈ {form, json}` when present;
otherwise `422 {fields: {probe_config: "..."}}`. Audit detail records
service/vendor/pair-count only — never a secret or the probe body.

## 4. Task create/update (changed) — `POST` / `PUT /.../tasks[/{id}]`

- Recurrence accepts the full `once` / `interval` shapes (parity with scan
  schedules); a past `once` ⇒ `422 {fields:{recurrence:"run_at must be in the
  future"}}` (FR-103).
- Body gains `dictionary_id` (optional) and `attempt_ceiling` (optional).

```jsonc
{
  "target_scope": ["10.10.0.5"],
  "port": 80,
  "service": "http",
  "dictionary_id": "<id>",
  "attempt_ceiling": null,
  "recurrence": { "type": "once", "run_at": "2026-11-01T09:00:00Z" },
  "enabled": true
}
```

Task serialization (GET `/tasks`) is unchanged in shape but the UI now renders
`enabled` and `next_run_at` as dedicated columns (3.1.2/3.1.3).

## 5. Run detail (changed) — `GET /api/tools/credential-check/runs/{run_id}`

Response adds per-attempt data for the result table (FR-113), and `status` may be
`running` (poll until terminal):

```jsonc
{
  "id": "<id>",
  "status": "running",            // or "completed" | "failed"
  "service": "http",
  "dictionary_id": "<id>",
  "attempt_ceiling": 5,
  "started_at": "...",
  "finished_at": null,
  "summary": { "compliant": 0, "non_compliant": 1 },
  "error_detail": null,            // set when status=failed
  "results": [
    {
      "address": "10.10.0.5",
      "result": "non_compliant",
      "attempts_made": 2,
      "matched_username": "admin",             // username only — never a password
      "matched_dictionary_entry": "<id>",
      "attempts": [
        { "username": "admin", "status": 401, "excerpt": "Login failed", "matched": false },
        { "username": "root",  "status": 200, "excerpt": "Dashboard",     "matched": true }
      ]
    }
  ]
}
```

**Invariant**: no response field, at any status, contains an attempted or matched
**password** (FR-114). `excerpt` is response-body-derived and secret-free.

## 6. Result page (new) — `GET /tools/credential-check/runs/{run_id}`

Server-rendered page (not JSON), styled like the scan `run_detail.html`: a
per-target table of attempts (target, username, response status/excerpt, result)
with the matched row highlighted. While `status == running`, the page polls
(~3s) and shows partial progress. Replaces the `alert()` result view (3.5).

## 7. Delete task — `DELETE /.../tasks/{id}`

Unchanged behavior from feature 007 (detaches historical runs, `204`). Noted here
only because `ToolCheckRun.dictionary_id` is likewise nullable on dictionary
deletion (`ondelete=SET NULL`), so deleting a dictionary never breaks a run's
history.

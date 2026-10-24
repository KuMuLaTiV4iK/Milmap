# Phase 1 Data Model: Credential-Check Tool Fixes

Scope: additive changes to four existing models in
`src/asset_dashboard/db/models.py`. No new tables. All new columns are nullable
or JSON-defaulted so `create_all` covers fresh databases and a tiny additive
migration covers existing ones (see **Migration** below). Secrets are never added
to any audit path; the only password-bearing field is the pre-existing
`DefaultCredentialEntry.credentials` reference catalog.

## 1. DefaultCredentialEntry (extended) — "a dictionary"

Per-service list of default credentials + how to probe HTTP/HTTPS with them.

| Field | Type | Notes |
|-------|------|-------|
| id | str (uuid) | existing PK |
| vendor | str | existing — the dictionary's human label/description (UI widens this field, 3.8) |
| service | str | existing — `sip\|ssh\|http\|https\|telnet\|ftp\|routeros-api` |
| credentials | JSON `[{username, secret}]` | existing — reference catalog (secrets allowed here only) |
| success_keywords | JSON `[str]` | existing — body keywords (still used as a default success rule) |
| **probe_config** | **JSON** (new, default `{}`) | HTTP/HTTPS form-probe settings; empty ⇒ defaults. Ignored by non-HTTP probes. |

`probe_config` shape (all keys optional; defaults in parentheses):

```jsonc
{
  "login_path": "/login",                 // ("/login")
  "method": "POST",                        // ("POST")
  "username_field": "username",            // ("username")
  "password_field": "password",            // ("password")
  "extra_fields": {"...": "..."},          // static form fields ({})
  "encoding": "form",                       // "form" | "json"  ("form")
  "fingerprint": {                          // optional GET-based gate
    "keywords": ["..."],                    //   body signatures that identify this form
    "status": [200]                         //   acceptable GET status(es)
  },
  "csrf": {                                 // optional anti-forgery token capture
    "source": "input",                      //   "input" (hidden field) | "cookie" | "header"
    "name": "csrf_token",                   //   field/cookie/header name on GET
    "field": "csrf_token"                   //   POST field to carry it in
  },
  "success": {"status": [200, 302], "keywords": ["Dashboard", "Logout"]},
  "failure": {"status": [401, 403], "keywords": ["Invalid", "Login failed"]}
}
```

**Validation**: `service ∈ ALLOWED_SERVICES`; `vendor` non-empty; each credential
has non-empty `username` and `secret`; `probe_config` (when present) is an object
and `method ∈ {GET, POST}`, `encoding ∈ {form, json}`. Unknown keys ignored.

**Success evaluation rule** (HTTP/HTTPS): matched = response satisfies `success`
(status in set OR any keyword in body, per configuration) AND NOT `failure`. When
`probe_config` is empty, fall back to the legacy rule (body contains any
`success_keywords`), but judged on the **POST** response, not a bare GET.

## 2. ToolTask (extended) — a scheduled credential check

| Field | Type | Notes |
|-------|------|-------|
| id, tool, target_scope, port, service, recurrence, enabled, next_run_at, overlap_policy, catch_up_policy, last_triggered_at, created_by | — | existing |
| **dictionary_id** | **str (uuid) FK → default_credential_entries.id, nullable, `ondelete=SET NULL`** | the chosen dictionary (3.2). Null ⇒ all dictionaries for the service (legacy behavior) |
| **attempt_ceiling** | **int, nullable** | operator ceiling (FR-108). Null ⇒ default = selected dictionary size |

Recurrence unchanged (shared `once`/`interval` shapes); the once/interval
**parity** is a UI/validation fix, not a schema change.

## 3. ToolCheckRun (extended) — one execution

| Field | Type | Notes |
|-------|------|-------|
| id, tool_task_id (`ondelete=SET NULL`, feature 007 fix), trigger, triggered_by_id, target_scope, port, service, status, started_at, finished_at, summary, archived | — | existing |
| **dictionary_id** | **str (uuid) FK → default_credential_entries.id, nullable, `ondelete=SET NULL`** | the dictionary used (snapshotted by id; credentials are read at start) |
| **attempt_ceiling** | **int, nullable** | effective ceiling recorded for the run |
| **error_detail** | **str (Text), nullable** | set when a background run fails (FR-117) |

`status` lifecycle (existing enum `RunStatus`): `RUNNING` committed immediately at
start (FR-112) → `COMPLETED` on normal finish → `FAILED` (with `error_detail`) on
worker exception. No `CANCELLED` path required for v1 (cred runs are bounded).

## 4. ToolCheckResult (extended) — per-target outcome

| Field | Type | Notes |
|-------|------|-------|
| id, run_id (`ondelete` via cascade relationship), address, result, attempts_made | — | existing |
| detail | JSON | existing — **extended** to carry the per-attempt list (below) |

`detail` shape (password-free, FR-114):

```jsonc
{
  "protocol": "http",
  "matched_username": "admin",        // username of the accepted credential, or null
  "matched_dictionary_entry": "<id>", // which dictionary row matched, or null
  "attempts": [
    {"username": "admin", "status": 401, "excerpt": "Login failed", "matched": false},
    {"username": "root",  "status": 200, "excerpt": "Dashboard",     "matched": true}
  ]
}
```

- `attempts[].username` — allowed (not a secret).
- `attempts[].status` — HTTP status (or protocol-appropriate code/label).
- `attempts[].excerpt` — short response excerpt for operator debugging; MUST NOT
  contain the attempted secret (it is populated from the response body only, per
  the existing `ProbeAttemptResult.response_excerpt` contract).
- **No `secret`/`password` key anywhere** in `detail` or the audit log.

## Result semantics (FR-110, FR-111)

- First `matched: true` ⇒ stop, `result = non_compliant`, record
  `matched_username`/`matched_dictionary_entry`.
- All candidates tried (attempts_made reached dictionary size) with no match ⇒
  `result = compliant`.
- A configured `attempt_ceiling` < dictionary size reached with no match ⇒
  `result = inconclusive` (the only remaining `inconclusive` path).

## ProbeAttemptResult (compliance/probes/base.py, extended)

| Field | Type | Notes |
|-------|------|-------|
| matched | bool | existing |
| response_excerpt | str | existing — body-only, secret-free |
| **status** | **int \| None** (new) | protocol status/code for the attempt row (e.g. HTTP 401) |

Non-HTTP probes may leave `status=None`; the result table shows a protocol label
instead.

## Migration

`Base.metadata.create_all` creates new tables only; it does **not** add columns to
existing tables. Changes here add columns to `default_credential_entries`,
`tool_tasks`, and `tool_check_runs`.

- **Fresh databases**: covered by `create_all` (run `python -m
  asset_dashboard.db.init`).
- **Existing databases**: add an idempotent additive step to `db/init.py`
  (`_add_missing_columns`): for each new column, check `PRAGMA table_info(<table>)`
  and `ALTER TABLE <table> ADD COLUMN <col> <type>` when absent (SQLite supports
  single-column adds with a constant/NULL default). FK-bearing columns
  (`dictionary_id`) are added as plain nullable columns; the `ondelete=SET NULL`
  behavior is enforced for fresh DBs and best-effort on existing ones (SQLite
  can't add a constraint to an existing column — acceptable, since the app also
  nulls references defensively, mirroring the feature-007 delete fix).

No data backfill is required: existing tasks/runs get `dictionary_id = NULL`
(= legacy "all dictionaries for service") and `attempt_ceiling = NULL` (= default
ceiling). Reference dictionaries get `probe_config = NULL` (= defaults).

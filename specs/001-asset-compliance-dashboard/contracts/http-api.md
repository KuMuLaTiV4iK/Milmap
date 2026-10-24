# HTTP API Contract: Asset Inventory & Compliance Management Dashboard

**Date**: 2026-10-21 | **Feature**: `001-asset-compliance-dashboard`

The application is a server-rendered web app; it exposes HTML pages (for operators) and a JSON API (used by HTMX partials and for contract testing). This contract defines the **interface** — paths, methods, inputs, outputs, status codes, and invariants — not the implementation. All responses are local-only (air-gapped).

## Conventions

- **Base**: `/` (same origin). JSON endpoints under `/api`; HTML pages at their own paths.
- **Auth**: every endpoint except `GET /login` and `POST /api/auth/login` requires an authenticated session cookie. Unauthenticated access to any other path → `401` (JSON) or redirect to `/login` (HTML) and discloses no data (FR-001).
- **Content types**: JSON endpoints accept/return `application/json`; HTML pages return `text/html`.
- **Errors**: JSON error shape `{ "error": { "code": string, "message": string, "fields"?: {field: message} } }`.
- **Concurrency**: profile mutations send/return a `version_token`; a stale token → `409 Conflict` (FR-042).
- **CSRF**: state-changing form/JSON posts require a CSRF token (server-rendered app).

---

## Authentication & accounts (FR-001–FR-006)

### `POST /api/auth/login`
- **Body**: `{ "username": string, "password": string }`
- **200**: `{ "ok": true }` + session cookie set.
- **401**: invalid credentials (increments failure counter; audited).
- **429**: account throttled/locked (`lock_until` in future) (FR-004).
- **Invariant**: password never logged; failure + lockout audited (FR-006).

### `POST /api/auth/logout`
- **200**: session invalidated.

### `POST /api/accounts` (create operator)
- **Body**: `{ "username": string, "password": string }`
- **201**: created.
- **422**: `{ error.fields.password }` when password length < 20 or policy fails (FR-002).

### `POST /api/accounts/{id}/password` (change)
- **Body**: `{ "current": string, "new": string }`
- **204**: changed.
- **422**: new password fails ≥20-char policy (FR-002) — old credential stays in force.

**Session rule**: idle beyond configured timeout → next request `401`/redirect (FR-005).

---

## Discovery Profiles (FR-007–FR-014, FR-042)

### `GET /api/profiles`
- **200**: `[{ id, name, description, target_scope, port_spec, has_schedule, version_token }]`

### `POST /api/profiles`
- **Body**: `{ name, description?, target_scope[], port_spec, scan_params{}, extracted_fields[], compliance_settings{}, cache_freshness_seconds, host_links[] }`
- **201**: full profile incl. `version_token`.
- **422**: validation errors — unparseable target, disallowed/invalid scan_params, malformed port_spec, missing required fields (FR-011). Each offending field in `error.fields`.

### `GET /api/profiles/{id}`
- **200**: full profile (incl. host_links, compliance_settings, version_token).
- **404**: unknown id.

### `PUT /api/profiles/{id}`
- **Body**: full profile + `version_token`.
- **200**: updated profile with incremented `version_token`.
- **409**: `version_token` stale — another operator modified it (FR-042); no silent overwrite.
- **422**: validation errors.

### `POST /api/profiles/{id}/duplicate`
- **201**: new independent profile copy (FR-007).

### `DELETE /api/profiles/{id}`
- **204**: profile removed from active use; **its historical runs remain** retrievable (FR-027).

---

## Discovery runs & results (FR-015–FR-021, FR-024, FR-025, FR-043)

### `POST /api/profiles/{id}/runs`
- **Body**: `{ "force_fresh"?: bool }`
- **202**: `{ run_id, status: "running" }` — run started.
- **200**: `{ run_id, status: "completed", served_from_cache: true, source_run_id }` — cache hit within freshness window and not force-fresh (FR-024).
- **409**: a run of this profile is already `running` (FR-043).
- **503**: global concurrency limit reached (FR-021) — retry later.

### `GET /api/runs/{run_id}`
- **200**: `{ id, profile_snapshot, trigger, status, served_from_cache, started_at, finished_at, summary, error_detail? }`
- Status may be `running | completed | cancelled | failed`. `failed` carries `error_detail` (e.g., nmap missing/underprivileged) (FR-020).

### `POST /api/runs/{run_id}/cancel`
- **200**: run set to `cancelled`, partial results retained (FR-017).

### `GET /api/runs/{run_id}/results`
- **200**: `[{ address, state, open_ports[{port,protocol,service,version}], extracted{}, management_link | null, findings[] }]`
- Empty target / no responding hosts → `[]` with run `summary.hosts = 0` (distinct from `failed`) (FR-020).
- `management_link: null` ⇒ UI shows link unavailable, row still renders (FR-019).

---

## History & caching (FR-022–FR-027)

### `GET /api/history`
- **Query**: `?profile_id=&status=&limit=&offset=`
- **200**: runs newest-first: `[{ id, profile_name, params_used, status, started_at, served_from_cache, summary }]` (FR-023). Loads < 3 s at ~5,000-host scale (SC-012).

### `GET /api/history/{run_id}`
- **200**: the run's full results as captured at run time (FR-023).

**Retention**: server applies configured retention predictably; no endpoint exceeds it (FR-026). (Admin retention config out of scope for this contract draft.)

---

## Scheduling (FR-028–FR-032)

### `GET /api/profiles/{id}/schedule`
- **200**: `{ recurrence, enabled, next_run_at, overlap_policy, catch_up_policy, last_triggered_at }` or `404` if none.

### `PUT /api/profiles/{id}/schedule`
- **Body**: `{ recurrence, enabled, overlap_policy?, catch_up_policy? }`
- **200**: saved schedule incl. computed `next_run_at` (FR-029).

### `DELETE /api/profiles/{id}/schedule`
- **204**: schedule removed; no further runs.

**Invariants**: a due schedule produces a DiscoveryRun identical in form to a manual run, honoring caching (FR-030); overlap with an in-progress run follows `overlap_policy` — never a duplicate concurrent run (FR-031, FR-043); missed-while-down handled by `catch_up_policy` (FR-032).

---

## Compliance (FR-033–FR-040) — surfaced within results

Compliance findings are returned inside `GET /api/runs/{run_id}/results[].findings` and summarized in run `summary`. No separate scan endpoint; compliance runs as part of a discovery run when enabled in `compliance_settings`.

**Finding shape**:
```json
{
  "control": "version_validity | default_credentials",
  "result": "compliant | non_compliant | unknown | inconclusive",
  "detail": {
    "version": { "matched_entry": "...", "status": "valid|invalid|unknown" },
    "credential": { "protocol": "sip|ssh|http|telnet", "attempts_made": 0, "matched_signature": "bool", "secret": "NEVER_RETURNED" }
  }
}
```

**Contract invariants (testable)**:
- `version_validity` results are produced with **zero external/network calls** (FR-034); version not in dataset ⇒ `unknown` (FR-035).
- `default_credentials`: `detail.credential.attempts_made ≤ 3` always; recorded attempt timestamps show ≥ 5 s spacing (FR-037, SC-008); cap reached w/o match ⇒ `inconclusive` (FR-038); body-keyword match ⇒ `non_compliant` (FR-036a/FR-039); no match within cap ⇒ `compliant`.
- No endpoint ever returns or logs the attempted secret in recoverable form (FR-039).

---

## HTML pages (operator UI)

| Path | Purpose |
|---|---|
| `GET /login` | sign-in page (only unauthenticated page) |
| `GET /` | dashboard overview (compliance posture of last runs) (SC-011) |
| `GET /profiles`, `GET /profiles/{id}` | profile list / editor |
| `GET /runs/{run_id}` | live run + results table with host links |
| `GET /history` | historical runs panel |
| `GET /schedules` | schedule management |

All pages require auth; all data-mutating interactions post to the JSON endpoints above (via HTMX).

# HTTP Contract Delta: Scan-Result Host Pivot & Run Configuration Window

Only the deltas from the current app are listed. All routes stay behind the
existing authentication gate and CSRF protection; roles unchanged (Operator +
Administrator).

## 1. EXTENDED — `POST /api/profiles/{profile_id}/runs`

Launches a run. **Backward compatible**: all new fields optional; omitting them
reproduces today's behavior.

### Request body (JSON)

| Field | Type | Req? | Current? | Notes |
|-------|------|------|----------|-------|
| `force_fresh` | boolean | no | existing | Unchanged. |
| `target_scope` | string[] \| null | no | existing | One-off target override; validated by `validate_target_scope`. |
| `port_spec` | string \| null | no | **NEW** | One-off port override; validated by `validate_port_spec`. |
| `scan_params` | object \| null | no | **NEW** | One-off scan-param override (e.g. `{"timing":"T4"}`); validated by `validate_scan_params` (allow-list keys only). |
| `extracted_fields` | string[] \| null | no | **NEW** | One-off extracted-fields override; subset of `{open_ports, service_version}`; validated by `validate_extracted_fields`. |

Notes:
- Compliance toggle and NSE selection are **not** overridable here — they are taken
  from the saved profile (FR-014).
- The response is unchanged: `202 {run_id, status}`; or `200 {run_id, status,
  served_from_cache, source_run_id}` when served from cache; or the existing error
  shapes.

### Responses

| Status | When | Body |
|--------|------|------|
| `202` | Run started | `{ "run_id", "status": "running" }` |
| `200` | Served from cache (only when no override present and `force_fresh` false) | `{ "run_id", "status", "served_from_cache": true, "source_run_id" }` |
| `400` | Effective target empty | `api_error("target_required", …)` |
| `400` | Any override fails validation | `validation_error({ "<field>": "<message>" })` |
| `404` | Profile not found | `api_error("not_found", …)` |
| `409` | Profile already running | `api_error("already_running", …)` |
| `503` | Concurrency limit reached | `api_error("concurrency_limit", …)` |

### Invariants (test targets)

- Overrides are written to the run's `params_used` / `profile_snapshot`; the
  `DiscoveryProfile` row is **unchanged** after the call (FR-017, SC-004).
- A disallowed `scan_params` key (e.g. `{"script":"x"}`) or any raw-flag-looking
  value is rejected with `400` — no such string reaches the nmap command line
  (FR-018).
- Cache is served only when no override is present and `force_fresh` is false
  (R2); any present override produces a fresh run.

## 2. NEW — `GET /profiles/{profile_id}/scan` (page)

Server-rendered **Scan Configuration page** (`scan_config.html`). Reused by **Run
now** and the **Scan selected with profile…** pivot.

### Query parameters

| Param | Type | Notes |
|-------|------|-------|
| `targets` | string | Optional. Comma-separated host addresses that pre-fill (override) the target field, e.g. `?targets=10.0.0.5,10.0.0.8`. When absent, the field is pre-filled from the profile's saved target. |

### Behavior

- Renders the four editable fields (target, port spec, timing, extracted fields)
  pre-filled from the profile, a read-only reflection of the version-validity
  compliance toggle and NSE selection, a live command preview (via the existing
  `POST /api/profiles/preview-command`), and a **Start Scan** button.
- **Start Scan** issues `POST /api/profiles/{profile_id}/runs` with only the
  fields the operator changed (unchanged targeted runs send an empty body → cache
  eligible). On success it navigates to `/runs/{run_id}` (today's post-launch
  destination).
- Start Scan is disabled until the target field is non-empty (FR-016); the server
  still returns `target_required` as a backstop.
- `404` if the profile does not exist.

## 3. EXTENDED — `GET /tools/credential-check` (page)

Unchanged route; now honors an optional pre-fill query parameter.

| Param | Type | Notes |
|-------|------|-------|
| `targets` | string | Optional. Comma-separated host addresses that pre-fill the **Run now** form's target-scope field. The operator still chooses port, service, and dictionary and presses Run (FR-008). |

No server behavior change beyond reading the param in the template; the check runs
under the unchanged central guard and is audited as today (FR-007, FR-009).

## 4. UNCHANGED — reused as-is

- `POST /api/profiles/preview-command` — live command preview for the scan page.
- `GET /api/profiles` — profile list for the "Scan selected with profile…" picker.
- `POST /api/tools/credential-check` — the actual credential-check launch (the
  pivot only pre-fills its form).
- `GET /runs/{run_id}` (page) and `GET /api/runs/{run_id}/results` — the results
  view being enhanced with selection; no API shape change.

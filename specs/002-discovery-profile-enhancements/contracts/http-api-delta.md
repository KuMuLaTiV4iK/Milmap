# HTTP API Delta: Feature 002

New and changed endpoints versus feature 001 (`specs/001-asset-compliance-dashboard/contracts/http-api.md`). All endpoints require an authenticated session; admin-only endpoints additionally require the `administrator` role and return **403** `{"error":{"code":"forbidden"}}` otherwise. Mutating endpoints require the existing CSRF header. Validation failures return **422** `{"error":{"code":"validation_error","fields":{...}}}`.

## Profiles (changed)

### `POST /api/profiles` and `PUT /api/profiles/{id}` (modified)

Request body changes:
- **Add** `selected_scripts: string[]` — NSE script ids; each MUST be an enabled allow-list entry (else 422 `selected_scripts`).
- `extracted_fields: string[]` — now accepted as-is (subset of `["open_ports","service_version"]` or empty); the former minimum-fields rule is removed.
- **Remove** `host_links` — ignored if sent (no `{host}` validation performed).
- `scan_params.timing` — defaults to `"T3"` when omitted on create.

Response serializer drops `host_links`, adds `selected_scripts`.

### `POST /api/profiles/preview-command` (new)

Returns the exact nmap argv a given (unsaved) profile payload would execute (FR-008).

- Body: same shape as `ProfileIn` (unsaved).
- 200: `{"command": ["nmap","-oX","-","-p","8291","-T3","--script","mikrotik-routeros-version","192.168.1.0/24"], "display": "nmap -oX - -p 8291 -T3 --script mikrotik-routeros-version 192.168.1.0/24"}`
- 422 on invalid payload (same validation as save).

## NSE allow-list (new, admin-only for writes)

- `GET /api/nse-scripts` → `[{id, script_id, description, safety, expected_ports, enabled}]` (any authenticated user; populates the profile checklist).
- `POST /api/nse-scripts` (admin) — body `{script_id, description?, safety?, expected_ports?}`. 201 entry. 422 on invalid/duplicate id. If `safety != "safe"`, response includes `{"warning":"non_safe_script"}` (non-blocking, FR-016). Audit `ALLOWLIST_CHANGE`.
- `PUT /api/nse-scripts/{id}` (admin) — update description/safety/expected_ports/enabled. Audit `ALLOWLIST_CHANGE`.
- `DELETE /api/nse-scripts/{id}` (admin) — 204. Profiles referencing the removed `script_id` can no longer run it (selection flagged/disabled; FR-013). Audit `ALLOWLIST_CHANGE`.

## Users & account (new)

### Self-service

- `POST /api/account/password` — change own password. Body `{current_password, new_password}`. Enforces the effective `password_min_length` (≥ 20 floor). 204 on success; 422 on policy failure; 401 if current is wrong. Audit `ACCOUNT_CHANGE`.

### Admin user management (admin-only)

- `GET /api/users` → `[{id, username, role, status}]`.
- `POST /api/users` — `{username, password, role?}` (role default `operator`). 201. Audit `ACCOUNT_CHANGE`.
- `PUT /api/users/{id}` — change `role` and/or `status` (activate/deactivate). Rejects (409 `last_admin`) if it would remove the last active administrator (FR-033). Deactivation invalidates the target's session at next action (FR-034). Audit `ACCOUNT_CHANGE`.
- `POST /api/users/{id}/reset-password` — `{new_password}`. Invalidates target's session. Audit `ACCOUNT_CHANGE`.

## Security settings (new, admin-only)

- `GET /api/settings/security` → `{password_min_length, lockout_threshold, lockout_duration_seconds, session_idle_timeout_seconds}`.
- `PUT /api/settings/security` — update any subset. `password_min_length` below **20** → 422 `{fields:{password_min_length:"must be at least 20"}}` (FR-032). Audit `CONFIG_CHANGE`.

## Standalone credential tool (new)

### On demand

- `POST /api/tools/credential-check` — body `{target_scope: string[], port: int, service: "sip"|"ssh"|"http"|"telnet"}`. Runs now, honoring the 3-attempt/≥5 s guard per target. 201 `{run_id}`. Audit `TOOL_CHECK`.
- `GET /api/tools/credential-check/runs` → list of `ToolCheckRun` summaries.
- `GET /api/tools/credential-check/runs/{id}` → run with per-target `ToolCheckResult` rows (`result`, `attempts_made`; never a secret).

### Scheduled tasks (shared scheduler)

- `GET /api/tools/credential-check/tasks` → `[{id, tool, target_scope, port, service, recurrence, enabled, next_run_at}]`.
- `POST /api/tools/credential-check/tasks` — `{target_scope, port, service, recurrence, overlap_policy?, catch_up_policy?}`. 201 with `next_run_at`. Audit `SCHEDULE_CHANGE`.
- `PUT /api/tools/credential-check/tasks/{id}` — edit/enable/disable. Audit `SCHEDULE_CHANGE`.
- `DELETE /api/tools/credential-check/tasks/{id}` — 204.

A scheduled task fires via `scheduling/engine.tick()` and produces a `ToolCheckRun` equivalent to an on-demand run (FR-021).

## Pages (new / changed, HTML)

- `GET /profiles` (changed) — each row shows an **Edit** button linking `GET /profiles/{id}` (the existing editor page).
- `GET /profiles/{id}` (changed editor) — real extraction checkboxes, `T3` pre-selected for new profiles, NSE checklist, effective-command preview, host-link field removed, `?` help annotations, Ukrainian labels.
- `GET /configuration` (new, authenticated) — change-own-password for all; users, security settings, and NSE allow-list sections for admins only.
- `GET /tools/credential-check` (new) — run-now form, run history, and schedule management for the standalone tool.
- All pages render the dark SOC theme, Ukrainian text, "Milmap" branding; nav shows admin-only entries only to administrators.

## Behavior notes

- The default-credential control is **removed** from discovery-profile runs; `GET /` dashboard posture reflects only `version_validity` from profile runs plus (optionally) the standalone tool's latest results.
- Technical identifiers in responses and the UI (`T3`, `-sV`, port numbers, script ids) are always literal English, never localized.

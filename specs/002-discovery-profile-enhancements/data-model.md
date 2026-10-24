# Data Model Delta: Feature 002

This feature **extends** the feature-001 schema (`src/asset_dashboard/db/models.py`). Only changes are described here; all 001 entities not mentioned are unchanged. One Alembic migration (`0002_*`) applies these changes.

## Changed entities

### OperatorAccount (modified)

Adds role support for the two-role model and bootstrap.

| Field | Type | Notes |
|---|---|---|
| `role` | Enum(`administrator`, `operator`) | **New.** Default `operator`. First account on a fresh install is set to `administrator` (FR-030). Governs admin-only functions (FR-027, FR-028, FR-031). |

Rules:
- At least one **active** `administrator` must always exist — deactivating/demoting the last one is rejected (FR-033).
- `status` (existing `active`/`disabled`) now also enforced at sign-in and invalidates sessions on admin deactivation/reset (FR-034).

### DiscoveryProfile (modified)

| Field | Type | Notes |
|---|---|---|
| `selected_scripts` | JSON list[str] | **New.** Allow-list NSE script ids applied via `--script` (FR-010). Validated against the current allow-list at save (FR-013). Default `[]`. |
| `extracted_fields` | JSON list[str] | **Behavior change.** No longer forced to include both fields; any subset of `{open_ports, service_version}` (or empty) is valid (FR-005, FR-006). |
| `scan_params.timing` | str in `{T0..T5}` | **Default change.** New profiles default to `T3` (FR-001). |
| `host_links` (relationship) | — | **Deprecated/unused.** No longer written or read by the API/UI; `HostLinkTemplate` rows are ignored (FR-004). Table retained to avoid a risky SQLite drop. |
| `compliance_settings.default_credentials` | bool | **Removed from use.** Profile runs no longer trigger the default-credential check (moved to the standalone tool; FR-020). `version_validity` remains. |

### DiscoveredAsset (modified)

| Field | Type | Notes |
|---|---|---|
| `management_link` | str/null | **No longer populated** by the runner and not rendered in result tables (FR-004). Column retained, left null. |
| `extracted` | JSON dict | **Behavior extension.** Per-host NSE script output is stored here under key `nse` as `{script_id: output_text}` (FR-011); **no new column** — reuses the existing `extracted` dict and persists in history with it. |

### AuditEventType (modified enum)

Add members (FR-014, FR-024, FR-029/031):
- `ALLOWLIST_CHANGE` — NSE allow-list add/update/remove.
- `CONFIG_CHANGE` — security-settings change.
- `TOOL_CHECK` — standalone credential-tool run outcome (counts/timings only; never secrets).

(`ACCOUNT_CHANGE` already exists and covers user management.)

## New entities

### NseScriptAllowlistEntry

Curated, admin-editable list of selectable NSE scripts (FR-010–FR-018). Seeded from `data/reference/nse_allowlist.json`.

| Field | Type | Notes |
|---|---|---|
| `id` | str(36) PK (uuid) | |
| `script_id` | str(128), unique, indexed | nmap script name, e.g. `mikrotik-routeros-version`. Pattern `^[a-z0-9][a-z0-9._-]*$`. |
| `description` | text/null | Operator-facing description. |
| `safety` | str(16) | `safe` \| `other` (reference to nmap category; `other` triggers the FR-016 warning). Default `safe`. |
| `expected_ports` | JSON list | Optional ports the script targets (drives the FR-019 "port not in scope" warning). |
| `enabled` | bool | Default true. Disabled entries are not selectable. |
| `created_by` / `created_at` / `updated_at` | str(36)/datetime | Provenance for audit. |

Validation: non-empty `script_id`, unique, pattern match (FR-018).

### SecuritySetting

Runtime, admin-editable account/session security settings (FR-032). Single effective row (or key/value rows) seeded from `config.py` defaults; unset keys fall back to config.

| Key | Type | Floor / rule |
|---|---|---|
| `password_min_length` | int | **Hard floor 20** — updates below 20 rejected (FR-032). |
| `lockout_threshold` | int | Positive int. |
| `lockout_duration_seconds` | int | Positive int. |
| `session_idle_timeout_seconds` | int | Positive int. |

Auth code (`passwords.py`, `sessions.py`, `throttle.py`) reads effective values from this store.

### ToolTask

A schedulable standalone-tool job, distinct from a profile `Schedule`, scanned by the shared scheduler (FR-020, FR-021).

| Field | Type | Notes |
|---|---|---|
| `id` | str(36) PK (uuid) | |
| `tool` | Enum(`default_credentials`) | Extensible for future tools. |
| `target_scope` | JSON list[str] | Explicit hosts/CIDRs/ranges (FR-020). |
| `port` | int | Port to check. |
| `service` | str(16) | `sip`\|`ssh`\|`http`\|`telnet` — selects catalog entries/probe. |
| `recurrence` | JSON | Same shapes as `Schedule.recurrence` (interval/daily/weekly). |
| `enabled` | bool | Default true. |
| `next_run_at` | datetime | Managed by `compute_next_run_at`. |
| `overlap_policy` | Enum(SKIP, QUEUE) | Reused from 001. |
| `catch_up_policy` | Enum(RUN_ONCE, SKIP) | Reused from 001. |
| `last_triggered_at` | datetime/null | |
| `created_by` | str(36)/null | |

Rule: no duplicate concurrent run of the same tool task (overlap policy, consistent with 001 scheduling).

### ToolCheckRun

A persisted standalone credential-tool execution (on demand or scheduled).

| Field | Type | Notes |
|---|---|---|
| `id` | str(36) PK (uuid) | |
| `tool_task_id` | str(36)/null FK | Null for on-demand runs. |
| `trigger` | Enum(MANUAL, SCHEDULED) | Reused enum. |
| `triggered_by_id` | str(36)/null FK → operator | Null for scheduled. |
| `target_scope` / `port` / `service` | JSON/int/str | As executed. |
| `status` | Enum(RUNNING, COMPLETED, FAILED) | |
| `started_at` / `finished_at` | datetime | |
| `summary` | JSON | Tally of per-target results. |

### ToolCheckResult

Per-target outcome within a `ToolCheckRun` (device-safety counts only; **no secrets**, FR-024).

| Field | Type | Notes |
|---|---|---|
| `id` | str(36) PK (uuid) | |
| `run_id` | str(36) FK → ToolCheckRun, indexed | |
| `address` | str(128) | Target host. |
| `result` | Enum(COMPLIANT, NON_COMPLIANT, INCONCLUSIVE) | From `check_default_credentials` (FR-023). |
| `attempts_made` | int | ≤ 3 (verifiable guard, FR-022). |
| `detail` | JSON | Protocol label, timings; never the attempted secret. |

## Reference data (new)

### `data/reference/nse_allowlist.json`

Seed for `NseScriptAllowlistEntry`, e.g.:

```json
[
  {"script_id": "mikrotik-routeros-version", "description": "Detect MikroTik RouterOS version on 8291", "safety": "safe", "expected_ports": [8291]},
  {"script_id": "banner", "description": "Grab service banners", "safety": "safe"}
]
```

## Entity relationship summary (new/changed)

```text
OperatorAccount(+role) 1─* ToolTask (created_by)      [new]
OperatorAccount        1─* ToolCheckRun (triggered_by)[new]
ToolTask 1─* ToolCheckRun 1─* ToolCheckResult         [new]
DiscoveryProfile(+selected_scripts) ─ references ─* NseScriptAllowlistEntry (by script_id) [new]
SecuritySetting (standalone)                          [new]
HostLinkTemplate                                      [retained, unused]
```

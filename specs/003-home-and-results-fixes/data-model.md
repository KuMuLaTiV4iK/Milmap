# Phase 1 Data Model: Home Page & Results Corrections

Deltas to the existing schema (features 001/002). Only **one** migration
(`0003`) carries DDL; everything else is stored in existing JSON columns or is
behavior-only. Entities not listed here are unchanged.

## Changed entities

### `Schedule` (migration 0003) — US6

Was: exactly one schedule per profile, no own target.

| Field | Change | Notes |
|-------|--------|-------|
| `profile_id` | **drop `UNIQUE`** | A profile may now have multiple schedules. FK stays `ON DELETE CASCADE`. SQLite requires an Alembic *batch* migration to drop the constraint. |
| `target_scope` | **new** `JSON`, default `[]` | The schedule's own target (FR-021a). Set at creation (defaults to the profile's saved target when present); used for every run of this schedule. Independent of later profile edits. |
| `label` | **new** `String(128)`, nullable | Optional human label to tell a profile's schedules apart. |

Validation (FR-021b): `target_scope` must be non-empty and pass
`validate_target_scope`; a schedule is never created/run with an empty/invalid
target. Existing fields (`recurrence`, `enabled`, `next_run_at`,
`overlap_policy`, `catch_up_policy`, `last_triggered_at`) are unchanged.

### `DiscoveryProfile` — US1 (no DDL)

- `target_scope` becomes **optional at save** (an empty list `[]` means
  "target-less", FR-003a). The column already defaults to `[]`; only
  `profiles/validation.py` changes (a present target is still validated). A
  target supplied at launch is **never** written back here (FR-003c).

### `DiscoveredAsset.open_ports` (JSON) — US3 (no DDL)

Each port entry gains a `state` field:

```jsonc
// before: {"port": 22, "protocol": "tcp", "service": "ssh", "version": "OpenSSH 7.4"}
// after:  {"port": 22, "protocol": "tcp", "state": "open",     "service": "ssh", "version": "OpenSSH 7.4"}
//         {"port": 8291,"protocol": "tcp", "state": "filtered", "service": "winbox", "version": null}
```

- `state` ∈ `open | filtered | closed | unknown` (from `ParsedPort.state`).
- All responding-host ports are stored (not only open), so the small-scan view
  can show per-port status. Rendering decides what to show (see below).
- Historical rows without `state` are treated as `open` by the view (backward
  compatible; no backfill).

### `DiscoveryRun.summary` (JSON) — US3 (no DDL)

- New key `ports_in_results`: count of distinct `(port, protocol)` pairs across
  the run's parsed hosts. Drives the small (`≤10`) vs large (`>10`) ports-column
  mode. `hosts` key is unchanged.

### `ComplianceFinding.detail` (JSON) — US4 (no DDL)

- For a `non_compliant` version finding, `detail` gains `expected_valid` (e.g.
  `"OpenSSH 9.x"`) drawn from the matching `valid` reference entry for the same
  product, alongside the existing `note`/`matched_entry`. Absent when no valid
  entry exists (carry only the note — never invented).

### `ReferenceVersionEntry` — US4 (no DDL)

- No schema change. Now also surfaced in an in-app view and **editable** (create
  / update / delete) by Operators and Administrators; each edit is audit-logged
  as `CONFIG_CHANGE` (FR-015b). Fields used by the view:
  `vendor, product, version_match, status (valid|invalid), note`.

## Unchanged (explicitly in scope to NOT alter)

- `OperatorAccount`, roles, `SecuritySetting`, `NseScriptAllowlistEntry`,
  `ToolTask`/`ToolCheckRun`/`ToolCheckResult`, the default-credential catalog,
  and the device-safety guard — all untouched (FR-018; Principle III).

## Derived / in-memory models (no persistence)

- **Ports display model** (`discovery/results_view.py`): per row, `{mode:
  "small"|"large", ports: [{port, protocol, state, service}], all_closed: bool}`.
  `small` lists every port with its state; `large` lists open-only; `all_closed`
  (large, no open ports) renders the "Всі порти closed або filtered" placeholder.
- **Home view model** (`web/dashboard.py`): `recent_profiles` (≤5, each with
  `is_target_less`), `recent_scans` (≤20, each with `posture` or
  `compliance="n/a"`).

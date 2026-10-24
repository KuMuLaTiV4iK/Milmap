# Phase 1 Data Model: Scan-Result Host Pivot & Run Configuration Window

**No persistent schema changes. No database migration.** This feature introduces
no new tables or columns. The entities below are either transient (client-side) or
already-existing records whose existing JSON fields now also carry one-off
overrides.

## Transient entities (not persisted)

### Host Selection

The set of host addresses the operator has ticked on a single run's results view.

| Attribute | Type | Notes |
|-----------|------|-------|
| addresses | list[string] | Host addresses exactly as shown in the results table; de-duplicated before use. |
| source_run_id | string | The run whose results are being viewed (context only). |

- **Lifecycle**: created by ticking checkboxes / **Select invalid-version hosts**;
  consumed by a single pivot action (navigation to the credential tool or Scan
  Configuration page); not persisted and need not survive a reload (FR-005).
- **Validation**: at least one address required to enable pivot actions (FR-002);
  **Select invalid-version hosts** adds `non_compliant` version rows to the current
  set (union, FR-003) and is unavailable when the run lacks version-validity
  evaluation (FR-004).

### Run Launch Configuration

The per-run settings shown in the Scan Configuration page and submitted on **Start
Scan**. Transient on the client; on submission its values become the launch
overrides (below).

| Field | Type | Editable in window | Source default |
|-------|------|--------------------|----------------|
| target_scope | list[string] | Yes | profile.target_scope (or `?targets=`) |
| port_spec | string | Yes | profile.port_spec |
| scan_params.timing | enum T0–T5 | Yes | profile.scan_params.timing |
| extracted_fields | list[string] | Yes | profile.extracted_fields |
| version-validity compliance | bool | **No (read-only)** | profile.compliance_settings.version_validity |
| selected NSE scripts | list[string] | **No (read-only)** | profile.selected_scripts |

- **Validation** (reuses `profiles/validation.py`): `validate_target_scope`,
  `validate_port_spec`, `validate_scan_params` (allow-list keys only),
  `validate_extracted_fields` (subset of `{open_ports, service_version}`). Raw
  nmap flags are impossible — only these vetted fields are accepted (FR-018).
- **One-off**: submitting never writes back to `DiscoveryProfile` (FR-017).

## Existing entities (unchanged schema; new usage)

### DiscoveryProfile (existing)

Read-only source of the window's defaults. **Never modified** by a launch. Fields
used: `target_scope`, `port_spec`, `scan_params`, `extracted_fields`,
`compliance_settings.version_validity`, `selected_scripts`.

### DiscoveryRun (existing)

The run created by **Start Scan**. Its existing JSON fields now carry the effective
(possibly overridden) parameters — no new column:

- `params_used` — already holds `target_scope`, `port_spec`, `scan_params`,
  `extracted_fields`, `selected_scripts`; now reflects the operator's one-off
  overrides when present.
- `profile_snapshot` — same values plus the profile `name`; the snapshot is the
  audit-visible record of what actually ran (Principle IV).
- `trigger` = `MANUAL`; `RUN_STARTED` audit event emitted as today.

### HostResult / ComplianceFinding (existing)

The results rows that are selectable. The **version-validity** finding’s
`result` (`compliant` | `non_compliant` | `unknown`) drives the invalid-version
auto-select predicate (`non_compliant` only). No change to how findings are
computed or stored.

### Credential Check run (existing, `ToolCheckRun`)

The credential pivot pre-fills the existing credential-tool run form
(`target_scope`); the resulting check is an ordinary `ToolCheckRun` governed by the
unchanged central guard (cooldown, ceiling, stop-on-match) and audited as today.
No change to its model.

## Relationships

```text
DiscoveryProfile ──(defaults, read-only)──▶ Run Launch Configuration ──(Start Scan)──▶ DiscoveryRun
                                                     ▲
Host Selection (ephemeral) ──(?targets=)─────────────┘  (scan pivot)
Host Selection (ephemeral) ──(?targets=)──▶ Credential-tool run form ──▶ ToolCheckRun  (cred pivot)
HostResult.version-validity finding ──(non_compliant)──▶ Host Selection (auto-select)
```

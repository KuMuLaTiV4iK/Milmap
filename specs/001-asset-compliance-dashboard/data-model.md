# Phase 1 Data Model: Asset Inventory & Compliance Management Dashboard

**Date**: 2026-10-21 | **Feature**: `001-asset-compliance-dashboard`

Entities derived from the spec's **Key Entities** and **Functional Requirements**. Types are logical (implementation maps to SQLAlchemy/SQLite). Timestamps are UTC. "Soft/implementation" notes are advisory; the authoritative rules are the referenced FRs.

## Entity overview & relationships

```text
OperatorAccount 1──* AuditLogEntry
OperatorAccount 1──* DiscoveryRun (triggered_by)

DiscoveryProfile 1──* DiscoveryRun
DiscoveryProfile 1──0..1 Schedule
DiscoveryProfile 1──* HostLinkTemplate
DiscoveryProfile *──* (embedded) extracted-field selection, compliance settings

DiscoveryRun 1──* DiscoveredAsset
DiscoveredAsset 1──* ComplianceFinding

ReferenceVersionEntry  (standalone, offline dataset)
DefaultCredentialEntry (standalone, offline catalog)
```

## OperatorAccount

Represents a local user who signs in. (FR-001–FR-006)

| Field | Type | Rules / Notes |
|---|---|---|
| id | UUID/int PK | |
| username | string, unique | required |
| password_hash | string | Argon2id; **never** store plaintext/recoverable (FR-003) |
| status | enum(active, disabled) | |
| failed_attempts | int | for throttling (FR-004) |
| lock_until | datetime? | set when throttle threshold exceeded |
| created_at / updated_at | datetime | |

**Validation**: password set/change MUST satisfy policy — **length ≥ 20** and other configured rules (FR-002); reject otherwise with reason.
**State**: active → disabled (admin); transient lock via `lock_until`.

## DiscoveryProfile

Reusable definition of what/how to discover. (FR-007–FR-014, FR-042)

| Field | Type | Rules / Notes |
|---|---|---|
| id | UUID/int PK | |
| name | string, unique | required |
| description | text | optional |
| target_scope | json | list of hosts/ranges/subnets; validated parseable (FR-008, FR-011) |
| port_spec | string | e.g., `5060-5062`, `22,80,443` (FR-009) |
| scan_params | json | allow-listed nmap tunables only (timing, `-sV` intensity, max-rate, host-timeout, discovery toggles) (FR-010, FR-011) |
| extracted_fields | json | selected telemetry fields; MUST allow at least open_ports + service/firmware version (FR-012) |
| compliance_settings | json | which controls run: `version_validity` on/off, `default_credentials` on/off + protocol(s) |
| cache_freshness_seconds | int | freshness window for cache reuse (FR-024) |
| version_token | int | optimistic-concurrency token; incremented each save (FR-042) |
| created_at / updated_at | datetime | |

**Relationships**: has many HostLinkTemplate; has 0..1 Schedule; has many DiscoveryRun.
**Validation**: required fields present; target_scope parses; scan_params all allow-listed with valid values; port_spec well-formed (FR-011).
**Deletion**: removing a profile MUST retain its historical runs (FR-027) — runs reference profile by id with profile metadata snapshotted on the run.

## HostLinkTemplate

URL template producing a per-host management link. (FR-013, FR-019)

| Field | Type | Rules / Notes |
|---|---|---|
| id | PK | |
| profile_id | FK → DiscoveryProfile | |
| label | string | shown in results (e.g., "Manage") |
| url_template | string | contains `{host}` (and optional placeholders); rendered per result row |

**Validation**: template must contain a host placeholder; row with unresolvable host renders link as unavailable (FR-019).

## DiscoveryRun

A persisted execution of a profile. (FR-016–FR-023, FR-030, FR-043)

| Field | Type | Rules / Notes |
|---|---|---|
| id | UUID/int PK | |
| profile_id | FK → DiscoveryProfile | nullable if profile later deleted; see profile_snapshot |
| profile_snapshot | json | name + params as used at run time (survives profile deletion) (FR-027) |
| trigger | enum(manual, scheduled) | FR-030 |
| triggered_by | FK → OperatorAccount? | null for scheduled |
| status | enum(running, completed, cancelled, failed) | FR-017, FR-020 |
| served_from_cache | bool | + source_run_id when true (FR-024) |
| source_run_id | FK → DiscoveryRun? | when cache reuse |
| started_at / finished_at | datetime | |
| params_used | json | exact nmap params for this run |
| summary | json | counts: hosts, open ports, compliance pass/fail/unknown/inconclusive |
| error_detail | text? | when failed (e.g., nmap missing/underprivileged) (FR-020) |

**State transitions**: running → completed | cancelled | failed. A cancelled run retains partial results (FR-017).
**Caching**: a run request within `cache_freshness_seconds` of a completed run for the same profile/scope MAY produce a `served_from_cache` run referencing the source (FR-024); force-fresh bypasses (FR-025).
**Concurrency**: at most one `running` run per profile (FR-043); global limiter caps concurrent runs (FR-021).

## DiscoveredAsset

A host found during a run. (FR-018, FR-019)

| Field | Type | Rules / Notes |
|---|---|---|
| id | PK | |
| run_id | FK → DiscoveryRun | |
| address | string | IP/hostname |
| state | enum(up, down, no_response) | empty-result handling (FR-020) |
| open_ports | json | list of {port, protocol, service, version/firmware} |
| extracted | json | profile's selected fields, resolved |
| management_link | string? | rendered from HostLinkTemplate; null ⇒ shown unavailable (FR-019) |

**Relationships**: has many ComplianceFinding.

## ComplianceFinding

Outcome of one control against one asset. (FR-033–FR-039)

| Field | Type | Rules / Notes |
|---|---|---|
| id | PK | |
| asset_id | FK → DiscoveredAsset | |
| control | enum(version_validity, default_credentials) | FR-033 |
| result | enum(compliant, non_compliant, unknown, inconclusive) | FR-035, FR-038 |
| detail | json | version check: matched reference entry / "unknown"; credential check: protocol, attempts_made (≤3), matched_signature (no secrets stored) (FR-039) |
| checked_at | datetime | |

**Invariants (credential_control)**: `attempts_made ≤ 3`; recorded attempts show ≥ 5 s spacing (FR-037); never stores attempted secrets in recoverable form (FR-039); cap reached without match ⇒ `inconclusive` (FR-038); keyword/signature match ⇒ `non_compliant` (FR-036a/FR-039); no match within cap ⇒ `compliant`.
**Invariants (version_control)**: evaluated with **zero external/network I/O** (FR-034); version absent from dataset ⇒ `unknown` (FR-035).

## Schedule

Recurrence attached to a profile. (FR-028–FR-032)

| Field | Type | Rules / Notes |
|---|---|---|
| id | PK | |
| profile_id | FK → DiscoveryProfile, unique | 0..1 per profile |
| recurrence | json | cron or interval definition |
| enabled | bool | FR-028 |
| next_run_at | datetime | displayed (FR-029) |
| overlap_policy | enum(skip, queue) | default skip (FR-031) |
| catch_up_policy | enum(run_once, skip) | missed-while-down handling (FR-032) |
| last_triggered_at | datetime? | |

## ReferenceVersionEntry  (offline dataset)

Locally maintained version-validity data. (FR-034, FR-035, FR-040)

| Field | Type | Rules / Notes |
|---|---|---|
| id | PK | |
| vendor | string | |
| product/service | string | |
| version_match | string | exact version or range expression |
| status | enum(valid, invalid) | invalid ⇒ outdated/non-compliant |
| note | text? | |

Seeded from `data/reference/version_validity.yaml`; editable offline; no network lookups.

## DefaultCredentialEntry  (offline catalog)

Known factory-default credentials + success signatures. (FR-036, FR-036a, FR-040)

| Field | Type | Rules / Notes |
|---|---|---|
| id | PK | |
| vendor | string | |
| service/protocol | enum(sip, ssh, http, telnet) | |
| credentials | json | list of {username, secret} to try (handled in-memory; results never persist the secret) |
| success_keywords | json | signatures matched against response body to confirm acceptance (FR-036a) |

Seeded from `data/reference/default_credentials.yaml`; editable offline.

## AuditLogEntry

Security-relevant event log. (FR-006)

| Field | Type | Rules / Notes |
|---|---|---|
| id | PK | |
| ts | datetime | |
| actor | FK → OperatorAccount? | null for system/scheduled |
| event_type | enum(signin_success, signin_failure, lockout, profile_change, run_started, run_finished, compliance_check, schedule_change, account_change) | |
| detail | json | includes credential-check attempt counts/timings for SC-008 verification; **no secrets** |

## Cross-entity validation & derived rules

- **Auth gate**: no entity is readable/writable without an authenticated session (FR-001).
- **Cache**: `served_from_cache` runs must reference a `source_run_id` within freshness window (FR-024).
- **Retention**: a configurable policy prunes old DiscoveryRun (+ children) predictably when thresholds reached (FR-026); profiles' runs survive profile deletion (FR-027).
- **Scale**: model and queries target ~5,000 assets and runs spanning a /22 (~1,024 addresses) with history list load < 3 s (SC-012) — index `DiscoveryRun(profile_id, started_at)` and `DiscoveredAsset(run_id)`.

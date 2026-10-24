# Feature Specification: Reliable Database Schema Upgrades

**Feature Branch**: `004-db-schema-upgrades`

**Created**: 2026-10-22

**Status**: Draft

**Input**: User description: "Reliable database schema upgrades — fix scheduling broken after in-place upgrade. After upgrading the app to v0.3 over an existing database, creating a schedule returns 'Could not create schedule' (HTTP 500) and the background scheduler heartbeat crashes every ~30s with `no such column: schedules.target_scope`. Root cause: the app has no mechanism to bring an existing database up to the current schema version; `create_all` creates missing tables but never alters existing ones, startup never applies migrations, and there is no baseline migration or version stamp, so there is no correct command an operator can run to migrate an existing database."

## Context & Problem

This is an air-gapped, single-operator, local tool. Operators install a new version of the
application **over their existing database** (profiles, run history, accounts, schedules) on an
isolated host. In the current release that upgrade silently corrupts the application's behavior:

- Creating a schedule fails with a server error ("Could not create schedule").
- The `/schedules` page returns Internal Server Error.
- The background scheduling heartbeat throws a database error roughly every 30 seconds, flooding
  the server log with tracebacks, for as long as the app runs.

The underlying cause is that the application has **no reliable way to bring an existing database to
the schema the running code expects**. New releases add columns and tables that older databases do
not have; the existing first-run setup step only creates missing tables and never alters existing
ones; nothing applies the prepared schema changes on upgrade; and there is no record in a database
of which schema version it is at. As a result, every release that changes the schema will break an
in-place upgrade in exactly this way, and the failure is silent until a feature touches the missing
structure at runtime.

This feature makes in-place upgrades safe and reliable: an operator can move an existing database to
the current schema version with one documented, repeatable, offline step; a behind-schema database
is never served silently; and the recovery of already-broken databases in the field is covered.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Upgrade in place without breaking anything (Priority: P1)

An operator running an older version installs the new version on the same host, on top of their
existing database, and follows the documented upgrade step. When they start the application, all of
their existing data is intact and every feature works — including scheduling: they can create, list,
edit, and delete schedules, and recurring schedules fire on time, with no database errors anywhere.

**Why this priority**: This is the reported production breakage. Without it, upgrading is a
data-and-availability hazard: the scheduling feature is fully down and the log fills with recurring
errors. It is the minimum viable outcome of this feature and directly restores the v0.3 behavior
that the broken upgrade hid (per-schedule target and label, multiple schedules per profile).

**Independent Test**: Take a database produced by the previous release, perform the upgrade step,
start the app, and exercise the full schedule lifecycle plus a recurring trigger — all succeed with
no "missing column / missing table" style error, and the database reports the current schema version.

**Acceptance Scenarios**:

1. **Given** a database created by the previous release (missing the newest schedule fields),
   **When** the operator runs the documented upgrade step, **Then** the database is brought to the
   current schema version and all prior data (accounts, profiles, run history, existing schedules)
   is preserved.
2. **Given** an upgraded database, **When** the operator creates a schedule with its own target and
   label, **Then** it is saved and listed without error.
3. **Given** an upgraded database with an enabled schedule that is due, **When** the recurring
   heartbeat runs, **Then** the scheduled run is triggered and no database error is logged.
4. **Given** an upgraded database, **When** the operator opens the `/schedules` page, **Then** it
   renders successfully instead of returning Internal Server Error.

---

### User Story 2 - Safe, idempotent, offline upgrade with a recovery copy (Priority: P2)

Before the upgrade step changes anything in the operator's real database, it makes a recovery copy,
so an interrupted or unexpected upgrade can be rolled back without data loss. Running the upgrade
step again when the database is already current makes no changes. The entire upgrade runs with no
network access.

**Why this priority**: The database holds the organization's real internal inventory and audit
history. An upgrade that mutates that data must be reversible and must be safe to re-run, and it must
honor the air-gapped constraint. This protects the data that User Story 1 migrates.

**Independent Test**: Run the upgrade step on an older database and confirm a recovery copy is
produced before any change; run it a second time and confirm it reports "already current" and makes
no modification; run it on a host with no network and confirm it completes.

**Acceptance Scenarios**:

1. **Given** an older database, **When** the upgrade step begins, **Then** a recovery copy of the
   database file is created before any schema change is applied.
2. **Given** a database already at the current schema version, **When** the operator runs the
   upgrade step again, **Then** it completes successfully and makes no changes (idempotent).
3. **Given** a host with no network connectivity, **When** the operator runs the upgrade step,
   **Then** it completes without attempting any network access.
4. **Given** the recovery copy cannot be created (e.g., insufficient disk space or permissions),
   **When** the upgrade step runs, **Then** it stops before modifying the database and reports why.

---

### User Story 3 - Fail fast and clearly on a schema/code mismatch (Priority: P3)

If the database is behind the version the running code expects (for example, the operator started
the app before running the upgrade step), the application refuses to serve against it and shows one
clear, actionable message telling the operator to run the upgrade step — instead of serving opaque
500s and emitting a recurring background crash.

**Why this priority**: Turns a silent, recurring, whole-feature outage into a single legible
instruction. It makes this class of bug impossible to ship undiagnosed in future, but the system is
still correct and usable once User Stories 1–2 are in place, so it is the lowest of the three.

**Independent Test**: Point the app at a deliberately out-of-date database and start it; confirm it
produces exactly one clear "database needs upgrading" message and that the background scheduler does
not emit a repeating error.

**Acceptance Scenarios**:

1. **Given** a database older than the running code, **When** the application starts, **Then** it
   reports a single clear message identifying the mismatch and directing the operator to the upgrade
   step.
2. **Given** that same state, **When** time passes, **Then** the background scheduling heartbeat does
   not emit a repeating database error (no traceback flood).
3. **Given** a database newer than the running code (a downgrade of the app), **When** the
   application starts, **Then** it refuses to run against it and says so, rather than silently
   operating on a schema it does not understand.

---

### Edge Cases

- **Legacy database with no version stamp**: Databases created by the current first-run setup carry
  no record of their schema version. The upgrade step MUST recognize such a database, reconcile it to
  a known version, and bring it current without duplicating or failing on structures that already
  exist.
- **Fresh install (no database yet)**: First-run setup MUST produce a database that is already at the
  current schema version and is correctly stamped, so the very next upgrade step is a no-op.
- **Database already current**: The upgrade step is a no-op and says so (idempotent).
- **Database ahead of code**: Treated as a mismatch the app refuses to serve against (User Story 3,
  scenario 3).
- **Interrupted upgrade** (power loss / killed process mid-step): The recovery copy from User Story 2
  allows the operator to restore the pre-upgrade state.
- **Backup target unavailable** (no space / no permission): Abort before mutating (User Story 2,
  scenario 4).
- **Concurrent start during upgrade**: The upgrade step and a running app must not operate on the
  database at the same time in a way that corrupts it; the operator performs the upgrade with the app
  stopped.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a single, documented operator step that brings an existing
  database to the schema version the running code expects.
- **FR-002**: The upgrade step MUST preserve all existing operator data — accounts, discovery
  profiles, run history and results, compliance findings, schedules, reference data, and audit log —
  with no loss.
- **FR-003**: The upgrade step MUST be idempotent: running it against a database that is already
  current MUST make no changes and MUST report that the database is already current.
- **FR-004**: The system MUST record, within each database, which schema version it is at, so that
  the current version can be compared against the version the code expects.
- **FR-005**: First-run setup MUST produce a database that is already at the current schema version
  and is recorded as such, so that a fresh install and an upgraded install converge on the same,
  correctly versioned schema.
- **FR-006**: The system MUST be able to recognize and reconcile a legacy database that has no
  recorded schema version (one produced by the previous first-run setup) and bring it current
  without failing on structures that already exist.
- **FR-007**: Before applying any schema change to the operator's database, the upgrade step MUST
  create a recovery copy of the database from which the pre-upgrade state can be restored.
- **FR-008**: If the recovery copy cannot be created, the upgrade step MUST stop before modifying the
  database and MUST report the reason.
- **FR-009**: The upgrade step MUST operate entirely offline, with no network access, and MUST NOT
  introduce any new runtime dependency.
- **FR-010**: On startup, if the database is behind the schema version the code expects, the
  application MUST NOT serve requests against it silently; it MUST fail fast with a single, clear,
  actionable message directing the operator to the upgrade step.
- **FR-011**: On startup, if the database is ahead of the schema version the code expects, the
  application MUST refuse to operate against it and MUST report the mismatch.
- **FR-012**: The background scheduling heartbeat MUST NOT repeatedly crash and flood the log when
  the database schema does not match the code; the startup fail-fast (FR-010/FR-011) MUST prevent the
  heartbeat from running against a mismatched schema.
- **FR-013**: After an upgrade, the full scheduling feature MUST work: create, list, edit, and delete
  schedules — each able to carry its own target and optional label, with multiple schedules allowed
  per profile — and recurring schedules MUST fire via the heartbeat, all without schema errors.
- **FR-014**: The documented setup and upgrade instructions (operator-facing docs) MUST be updated so
  that an operator can both install fresh and upgrade in place without needing any knowledge of the
  underlying migration tooling.
- **FR-015**: A database already broken in the field by a prior in-place upgrade (missing the newest
  columns, no version stamp) MUST be recoverable to a correct, current, versioned state by the
  documented upgrade step, without data loss.

### Key Entities *(include if feature involves data)*

- **Schema version record**: A marker stored inside each database identifying the schema version it
  is currently at. Used to compare a database against the version the running code expects, and to
  decide whether an upgrade is needed, a no-op, or a refuse-to-run mismatch.
- **Schema change (migration)**: An ordered, named unit of schema change that moves a database from
  one version to the next. The ordered set of these defines the path from any older version to
  current, including a baseline that establishes the earliest known schema.
- **Recovery copy**: A pre-upgrade copy of the database file taken before any change is applied, from
  which the operator can restore the prior state if an upgrade is interrupted or unwanted.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator upgrading from the previous release and completing the documented upgrade
  step reaches a fully working scheduling feature — creating, listing, editing, and deleting a
  schedule and a recurring trigger all succeed — with zero schema-related errors in the server log.
- **SC-002**: A database produced by a fresh install and a database produced by upgrading an older
  one have the identical structure (same tables, columns, and indexes) and report the same schema
  version.
- **SC-003**: Running the upgrade step a second time completes and makes no changes to the database.
- **SC-004**: With a database deliberately older than the code, startup produces exactly one clear
  "database needs upgrading" message and the background scheduler emits no repeating error over a
  sustained run.
- **SC-005**: After an upgrade, no operator data is lost — every account, profile, run, result,
  schedule, reference entry, and audit record present before the upgrade is present after it.
- **SC-006**: The entire upgrade completes on a host with no network access.
- **SC-007**: All existing automated tests for prior features (001, 002, 003) continue to pass.

## Assumptions

- The project already includes a migration tool as a dependency; this feature uses the existing tool
  rather than adding a new runtime dependency (per FR-009).
- The runtime database is a single local file under the deployment's `data/` directory on a single
  host, operated by a single operator — consistent with the project's offline, single-process design.
- The operator performs the upgrade step with the application stopped (no second process writing to
  the database during the upgrade). This matches the single-operator, single-host deployment and
  avoids concurrent-writer corruption.
- Legacy databases in the field were created by the previous first-run setup and therefore carry the
  full older schema but no recorded schema version; reconciling them (FR-006) means recording the
  version they correspond to and then applying the remaining ordered changes.
- The default, informed design is: the upgrade is an explicit documented step (not an automatic
  startup mutation), and startup instead *detects and refuses* a behind-schema database (FR-010).
  This keeps application startup non-destructive and makes the operator's upgrade deliberate and
  auditable; automatic-on-startup upgrading is intentionally out of scope for this feature and may be
  reconsidered later.
- "Recovery copy" (FR-007) means a copy of the database file taken before mutation; for the local
  single-file database this is a straightforward file copy under local storage.

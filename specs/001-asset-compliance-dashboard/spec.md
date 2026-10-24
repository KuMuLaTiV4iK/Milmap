# Feature Specification: Asset Inventory & Compliance Management Dashboard

**Feature Branch**: `001-asset-compliance-dashboard`

**Created**: 2026-10-21

**Status**: Draft

**Input**: User description: "Internal, air-gapped Asset Inventory and Compliance Management Dashboard. Local web app with strict local authentication (username + password ≥ 20 chars). Web UI to define and manage Asset Discovery Profiles that orchestrate internal telemetry tooling (nmap) to map internal infrastructure, with full CRUD, customizable scan parameters to optimize discovery time, per-profile selection of telemetry fields (open ports, service versions) and clickable links to internal host-management pages in the results table. Persistent storage with a dedicated panel for historical discovery runs (results cached to avoid redundant network load). A job-scheduling engine for discovery profiles. Example profile 'VoIP Infrastructure Audit': map VoIP endpoints (ports 5060-5062) for firmware versions and verify compliance against known default vendor credentials — a guarded authentication check limited to 3 attempts with a 5-second cooldown to avoid locking out devices; all version-validity checks are performed offline."

## Context & Scope

This is an **internal, defensive network-administration tool** operated by the organization's own Network Systems Administrators against the organization's own, authorized internal infrastructure on an **air-gapped network** (no internet access). Its purpose is asset inventory and security-compliance hygiene: knowing what is on the network, what services and firmware versions are running, and whether any devices are still exposed with factory-default credentials.

The application runs locally. Because the environment is air-gapped, every reference dataset (firmware/version validity data, the catalog of known default vendor credentials) is maintained and updated offline, inside the deployment.

## Clarifications

### Session 2026-10-21

- Q: For the default-credential compliance check, should the system make real (rate-limited) authentication attempts against live devices, or determine the result without authenticating? → A: Real, strictly bounded attempts (Option A). A device is confirmed to accept a default credential when the **body of its post-authentication response matches expected success keywords/signatures** (sourced from the local catalog per vendor/service), not merely a protocol-level status.
- Q: What scale of infrastructure must a single run and the overall inventory support? → A: Medium — up to ~5,000 hosts total; a single run may cover one or more /24–/22 subnets (up to ~1,024 addresses per /22).
- Q: Will multiple operators use the dashboard concurrently, or one at a time? → A: A few operators may act concurrently (Option B). The system must detect/prevent conflicting edits (no silent overwrite) and duplicate concurrent runs of the same profile, but need not scale to large teams.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Secure local access to the dashboard (Priority: P1)

A Network Systems Administrator opens the local dashboard and must sign in with a local username and password before seeing or doing anything. Because the host and the data it holds are sensitive, the application enforces a strong password policy (minimum 20 characters) and protects the sign-in against repeated guessing.

**Why this priority**: The dashboard exposes the organization's full internal asset map and compliance findings. Nothing else in the product may be reachable without authentication, so this gate is the foundation every other story depends on.

**Independent Test**: Install the app, create an operator account, and confirm that (a) no page or action is reachable while signed out, (b) a password shorter than 20 characters is rejected at account creation and password change, and (c) a correct credential grants an authenticated session.

**Acceptance Scenarios**:

1. **Given** an unauthenticated visitor, **When** they request any application page or action, **Then** they are redirected to sign-in and no inventory or profile data is disclosed.
2. **Given** an operator creating or changing a password, **When** the password is shorter than 20 characters or fails another policy rule, **Then** the change is rejected with a clear explanation and the old credential remains in force.
3. **Given** a valid username and password, **When** the operator signs in, **Then** an authenticated session begins and the dashboard is shown.
4. **Given** repeated failed sign-in attempts for an account, **When** a configured threshold is exceeded, **Then** further attempts are throttled/temporarily blocked and the events are recorded in the audit log.
5. **Given** an authenticated session that has been idle beyond the configured timeout, **When** the operator next acts, **Then** the session is expired and re-authentication is required.

---

### User Story 2 - Define and manage Asset Discovery Profiles (Priority: P1)

An administrator creates reusable **Asset Discovery Profiles** that describe what to map and how. A profile captures the target scope (hosts, ranges, or subnets), which ports/services to look at, tunable discovery parameters used to optimize how long a scan takes, which telemetry fields to extract (e.g., open ports, service/firmware versions), and templates for clickable links that take the operator from a result row to the matching internal host-management web page. Profiles can be created, viewed, edited, duplicated, and deleted.

**Why this priority**: Profiles are the central object of the product; discovery, history, scheduling, and compliance all operate on them. Without profile management there is nothing to run.

**Independent Test**: Create a profile (e.g., "VoIP Infrastructure Audit" targeting ports 5060-5062), edit its parameters and extracted-field selection, duplicate it, and delete it — verifying each change persists and is reflected in the profile list.

**Acceptance Scenarios**:

1. **Given** an authenticated administrator, **When** they create a profile with a name, target scope, port selection, discovery parameters, selected telemetry fields, and host-management link template, **Then** the profile is saved and appears in the profile list.
2. **Given** an existing profile, **When** the administrator edits any field and saves, **Then** the updated values persist and are used by subsequent runs.
3. **Given** an existing profile, **When** the administrator duplicates it, **Then** a new independent copy is created without affecting the original.
4. **Given** an existing profile, **When** the administrator deletes it, **Then** it no longer appears for new runs or scheduling, while its already-recorded historical runs remain viewable.
5. **Given** a profile being saved, **When** required fields are missing or discovery parameters are invalid (e.g., malformed target or disallowed option), **Then** the save is rejected with a specific, actionable validation message.
6. **Given** a profile, **When** the administrator adjusts its discovery parameters to trade thoroughness for speed, **Then** the profile records the chosen trade-off for use by future runs.

---

### User Story 3 - Run a discovery and review results with host links (Priority: P1)

An administrator runs a profile on demand. The system orchestrates the underlying telemetry tooling to map the targets, extracts the configured fields, and presents the findings in a results table. Each discovered host offers a clickable link to its internal host-management web page, so the operator can jump straight from a finding to acting on the device.

**Why this priority**: Running a profile and reading its results is the core value delivery — this is the moment the administrator learns what is actually on the network.

**Independent Test**: Run a saved profile against a known target and confirm the results table shows the configured telemetry fields for each responding host and that the host-management link opens the correct internal page for that host.

**Acceptance Scenarios**:

1. **Given** a saved profile, **When** the administrator starts a run, **Then** progress is shown and, on completion, a results table lists each responding host with the profile's selected telemetry fields (e.g., open ports, service/firmware versions).
2. **Given** a results table, **When** the administrator clicks a host's management link, **Then** the configured internal host-management page for that host opens.
3. **Given** a running discovery, **When** the administrator cancels it, **Then** the run stops and is recorded as cancelled with any partial results captured.
4. **Given** a target that is unreachable or returns no responding hosts, **When** the run completes, **Then** the results clearly indicate an empty/!no-response result rather than an error or a blank screen.
5. **Given** the host for a result row has no configured management page, **When** results render, **Then** the row still displays and the link is shown as unavailable rather than broken.

---

### User Story 4 - Historical runs and result caching (Priority: P2)

Every discovery run is stored persistently. A dedicated panel lists past runs with their timestamps, the profile and parameters used, and their outcomes, so administrators can review and compare results over time. To avoid putting redundant load on the network, the system can serve recent results from cache when a fresh scan is not needed, and lets the operator force a fresh run when it is.

**Why this priority**: Historical visibility and avoiding redundant network load are explicit goals, but they build on the ability to create and run profiles (P1), so they follow once that core exists.

**Independent Test**: Run a profile twice in quick succession and confirm the second request can be served from cache within the freshness window; confirm both runs (or the cache reuse) are visible in the history panel with correct timestamps and the profile/parameters used.

**Acceptance Scenarios**:

1. **Given** completed runs exist, **When** the administrator opens the history panel, **Then** runs are listed with timestamp, profile name, parameters used, status, and a summary of findings, newest first.
2. **Given** a historical run, **When** the administrator opens it, **Then** its full results table (including host links) is shown as it was at run time.
3. **Given** a recent cached result within the configured freshness window, **When** the administrator requests a run of the same profile/scope, **Then** the cached result can be reused (clearly labelled as cached, with its original time) instead of re-scanning the network.
4. **Given** a cached result is available, **When** the administrator chooses "force fresh", **Then** a new scan runs and its result supersedes the cache for future freshness checks.
5. **Given** stored history, **When** data retention or storage limits are reached, **Then** the system applies the configured retention policy predictably rather than failing.

---

### User Story 5 - Scheduled discovery jobs (Priority: P2)

An administrator schedules a profile to run automatically on a recurring basis (for example, nightly or weekly), so inventory and compliance data stay current without manual effort. Schedules can be enabled, disabled, and edited, and the system shows when each will next run.

**Why this priority**: Automation keeps data fresh and is a stated requirement, but it depends on profiles and runs already working, so it is valuable after the P1 core.

**Independent Test**: Attach a schedule to a profile, confirm the next-run time is displayed, let it trigger (or simulate the trigger), and confirm a run is produced and recorded in history exactly as a manual run would be.

**Acceptance Scenarios**:

1. **Given** a profile, **When** the administrator defines a recurring schedule, **Then** the schedule is saved and the next run time is displayed.
2. **Given** a schedule is due, **When** its time arrives, **Then** a discovery run starts automatically and is recorded in history, respecting the profile's caching settings.
3. **Given** a schedule, **When** the administrator disables or edits it, **Then** future runs follow the new state and no further runs occur while disabled.
4. **Given** a scheduled run is triggered while a previous run of the same profile is still in progress, **When** the overlap is detected, **Then** the system prevents a conflicting concurrent run per the configured overlap policy (e.g., skip or queue) rather than launching duplicates.
5. **Given** the application was not running when a schedule was due, **When** it next starts, **Then** missed-run handling follows the configured catch-up policy predictably.

---

### User Story 6 - Compliance auditing: offline version validity and guarded default-credential checks (Priority: P2)

For profiles configured to audit compliance (such as "VoIP Infrastructure Audit"), the system evaluates each discovered asset against compliance rules. Version and firmware validity are checked **offline** against a locally maintained reference dataset — no external lookups, consistent with the air-gapped environment. The system can also verify whether a device still accepts **known factory-default vendor credentials**, a standard security-hygiene finding. To avoid locking devices out, this check is strictly guarded: at most **3 attempts per target** with a **5-second cooldown between attempts**. Each asset is flagged compliant, non-compliant, or unknown, and findings surface in the results table.

**Why this priority**: Compliance is a headline goal and the differentiator of the product, but it layers on top of discovery results (P1) and benefits from history (P2), so it follows the core.

**Independent Test**: Run the "VoIP Infrastructure Audit" profile against a test endpoint and confirm (a) its firmware version is evaluated offline against the local reference dataset and flagged valid/invalid/unknown, and (b) the default-credential check performs at most 3 attempts with a 5-second gap between them and reports whether default credentials are still in use — without exceeding those limits.

**Acceptance Scenarios**:

1. **Given** a discovered asset with an extracted firmware/service version, **When** compliance evaluation runs, **Then** the version is checked against the local offline reference dataset and the asset is flagged valid, invalid/outdated, or unknown (version not in the dataset) — with no external/network lookup for the validity check.
2. **Given** a compliance profile that checks default credentials, **When** the check runs against a target, **Then** it makes no more than 3 authentication attempts and waits at least 5 seconds between consecutive attempts.
3. **Given** an attempted default credential whose post-authentication response body matches the expected success keywords/signatures for that vendor/service, **When** the check completes, **Then** the device is confirmed to accept default credentials and the asset is flagged non-compliant ("default credentials in use") in the results and history.
4. **Given** a target where no attempted default credential produces a response body matching the success keywords within the attempt limit, **When** the check completes, **Then** the asset is flagged compliant for that control (no default credentials detected).
5. **Given** the attempt limit or cooldown is in effect, **When** the limit is reached before a conclusive result, **Then** the check stops and the asset is flagged "inconclusive" rather than continuing to attempt and risking a device lockout.
6. **Given** compliance findings exist, **When** the administrator reviews a result or historical run, **Then** non-compliant and inconclusive assets are clearly distinguished from compliant ones.

---

### Edge Cases

- **Empty or unreachable target scope**: run completes with a clearly labelled "no responding hosts" result, not an error.
- **Oversized target range**: a profile targeting a very large scope must remain responsive, honor its time-optimization parameters, and surface progress and resource limits rather than hanging.
- **Underlying telemetry tool unavailable or lacking privileges**: the system reports a clear, actionable error and records the run as failed rather than silently producing empty results.
- **Invalid or disallowed scan parameters**: rejected at profile-save time against an allowed-parameter policy, so a run never executes an unvalidated option.
- **Version not present in the offline reference dataset**: flagged "unknown" (neither compliant nor non-compliant) so stale reference data is visible, not misreported.
- **Default-credential check reaching the attempt/cooldown limit**: stops immediately and reports "inconclusive"; never exceeds 3 attempts or shortens the 5-second cooldown.
- **Overlapping scheduled and manual runs of the same profile**: overlap policy prevents conflicting concurrent runs.
- **Cache hit vs. force-fresh**: operator can always distinguish cached results (with original timestamp) from freshly scanned ones and can force a fresh scan.
- **Concurrent edits to the same profile** by two operators: the system prevents silent overwrite (e.g., detects the conflict).
- **Host-management link with no page for a given host**: the row renders and the link is shown unavailable, never broken.
- **Password change mid-session** or account with weak legacy password: policy is enforced on next change; a sub-policy password cannot be set.
- **Deleting a profile with history**: the profile is removed from active use while its historical runs remain viewable.

## Requirements *(mandatory)*

### Functional Requirements

#### Authentication & Access Control

- **FR-001**: The system MUST require successful local authentication (username + password) before any page, data, or action is accessible.
- **FR-002**: The system MUST enforce a password policy requiring a minimum length of 20 characters, applied at account creation and at every password change, rejecting non-compliant passwords with a clear reason.
- **FR-003**: The system MUST store credentials only locally (no external identity provider or network dependency), consistent with the air-gapped environment, and MUST never store passwords in recoverable/plaintext form.
- **FR-004**: The system MUST throttle or temporarily block sign-in after a configurable number of consecutive failed attempts to resist brute-force guessing.
- **FR-005**: The system MUST maintain authenticated sessions with a configurable idle timeout and provide an explicit sign-out.
- **FR-006**: The system MUST record security-relevant events (sign-in success/failure, lockouts, profile changes, run executions, compliance checks) in an audit log.

#### Asset Discovery Profiles (CRUD & configuration)

- **FR-007**: Administrators MUST be able to create, view, edit, duplicate, and delete Asset Discovery Profiles.
- **FR-008**: A profile MUST capture a target scope expressed as hosts, ranges, and/or subnets.
- **FR-009**: A profile MUST allow selection of the ports/services to examine (including explicit ranges such as 5060-5062).
- **FR-010**: A profile MUST allow customization of discovery parameters that tune the thoroughness/speed trade-off to optimize discovery time, and MUST record the chosen settings for reuse.
- **FR-011**: The system MUST validate profile discovery parameters against an allowed-parameter policy at save time and reject malformed targets or disallowed options with specific messages.
- **FR-012**: A profile MUST allow the administrator to select which telemetry fields are extracted and displayed (at minimum: open ports and service/firmware versions).
- **FR-013**: A profile MUST allow definition of one or more host-management link templates that produce, for each result host, a clickable link to that host's internal management web page.
- **FR-014**: The system MUST persist profiles so they survive application restarts.

#### Discovery Execution & Results

- **FR-015**: The system MUST orchestrate the underlying internal telemetry tooling (nmap) to execute a profile against its target scope using the profile's configured parameters.
- **FR-016**: The system MUST allow an administrator to start a profile run on demand and MUST show run progress and completion status.
- **FR-017**: The system MUST allow an in-progress run to be cancelled, recording it as cancelled and retaining any partial results.
- **FR-018**: On completion, the system MUST present results in a table showing, per responding host, the profile's selected telemetry fields.
- **FR-019**: Each result row MUST render the configured host-management link as a clickable link, and MUST indicate clearly when no management page is configured/available for that host.
- **FR-020**: The system MUST represent an empty result (no responding hosts) and a failed run (e.g., tooling unavailable) distinctly and clearly, never as a blank or misleading success.
- **FR-021**: The system MUST limit and manage concurrent discovery activity so that large or simultaneous runs do not overwhelm the host or the network.

#### Persistence, History & Caching

- **FR-022**: The system MUST persistently store every discovery run, including timestamp, the profile and parameters used, status, and the full result set.
- **FR-023**: The system MUST provide a dedicated UI panel listing historical runs (newest first) with timestamp, profile, parameters, status, and a findings summary, and allow opening any run to view its full results as captured.
- **FR-024**: The system MUST support serving recent results from cache within a configurable freshness window to avoid redundant network scans, clearly labelling cached results with their original run time.
- **FR-025**: The system MUST allow an administrator to force a fresh scan that bypasses and refreshes the cache.
- **FR-026**: The system MUST apply a configurable data-retention policy to historical runs predictably when storage limits or retention thresholds are reached.
- **FR-027**: Deleting a profile MUST NOT delete its already-recorded historical runs; those MUST remain viewable.

#### Job Scheduling

- **FR-028**: The system MUST allow administrators to schedule profiles to run automatically on a recurring basis and to enable, disable, and edit those schedules.
- **FR-029**: The system MUST display the next scheduled run time for each schedule.
- **FR-030**: A scheduled run MUST produce and record a discovery run identical in form to a manual run, respecting the profile's caching settings.
- **FR-031**: The system MUST prevent conflicting concurrent runs of the same profile when a scheduled trigger overlaps an in-progress run, following a configurable overlap policy (e.g., skip or queue).
- **FR-032**: The system MUST follow a configurable catch-up policy for schedules that were due while the application was not running.

#### Compliance Auditing

- **FR-033**: The system MUST allow a profile to enable compliance evaluation of discovered assets and MUST surface each asset's compliance outcome in the results and history.
- **FR-034**: The system MUST evaluate extracted service/firmware versions against a locally maintained, offline reference dataset, performing the validity check with no external or network lookup.
- **FR-035**: The system MUST flag each evaluated asset as compliant (valid), non-compliant (invalid/outdated), or unknown (version not present in the reference dataset).
- **FR-036**: The system MUST support a default-credential compliance check that performs real, strictly rate-limited authentication attempts against a discovered device over its service protocol (e.g., SIP for VoIP, and SSH/Telnet/HTTP for others) using known factory-default vendor credentials from a locally maintained catalog.
- **FR-036a**: The system MUST determine whether an authentication attempt succeeded by matching the body of the device's response against expected success keywords/signatures defined per vendor/service in the local catalog; a response-body keyword match (not merely a protocol-level status code) constitutes confirmation that the default credential was accepted.
- **FR-037**: The default-credential check MUST make no more than 3 authentication attempts per target and MUST enforce a cooldown of at least 5 seconds between consecutive attempts, specifically to avoid locking out target devices.
- **FR-038**: When the attempt limit or cooldown prevents a conclusive result, the system MUST stop and record the asset as "inconclusive" rather than continuing to attempt.
- **FR-039**: The system MUST flag devices that still accept default credentials as non-compliant ("default credentials in use") and MUST NOT persist the specific credential secrets used during the check in recoverable form.
- **FR-040**: The system MUST maintain the offline reference datasets (version validity data and default-credential catalog) as locally updatable data, since the environment has no internet access.

#### Multi-Operator Concurrency

- **FR-041**: The system MUST support a few operators acting concurrently without requiring large-team scaling.
- **FR-042**: The system MUST detect and prevent conflicting profile edits: a save to a profile that another operator modified since it was loaded MUST be rejected or flagged for the operator to reconcile, with no silent overwrite.
- **FR-043**: The system MUST prevent duplicate concurrent runs of the same profile regardless of trigger (two operators manually, or a manual trigger overlapping a scheduled one), consistent with the overlap policy in FR-031.

### Key Entities *(include if feature involves data)*

- **Operator Account**: A local user who signs in. Attributes: username, protected password material, account status, lockout/throttle state, audit trail. (All operators are administrators unless a role model is later introduced — see Assumptions.)
- **Asset Discovery Profile**: The reusable definition of a discovery. Attributes: name, description, target scope (hosts/ranges/subnets), port/service selection, discovery parameters (speed/thoroughness tuning), selected telemetry fields, host-management link template(s), compliance settings (which controls to evaluate), caching/freshness settings, optional schedule reference.
- **Discovery Run**: A persisted record of one execution of a profile. Attributes: timestamp, originating profile and the exact parameters used, trigger (manual/scheduled), status (running/completed/cancelled/failed), whether served from cache, and the full result set.
- **Discovered Asset / Host Result**: A host found during a run. Attributes: host identifier/address, open ports, detected services and service/firmware versions, extracted telemetry fields, resolved host-management link, associated compliance findings.
- **Compliance Finding**: The outcome of evaluating one control against one asset. Attributes: control type (version validity / default credentials), result (compliant / non-compliant / unknown / inconclusive), supporting detail, timestamp.
- **Schedule**: The recurrence attached to a profile. Attributes: recurrence definition, enabled state, next-run time, overlap policy, catch-up policy.
- **Cached Result**: A recent run result eligible for reuse. Attributes: source run reference, original run time, freshness window, scope it satisfies.
- **Version Reference Dataset**: Locally maintained, offline data mapping services/firmware to validity status, used for version compliance checks.
- **Default-Credential Catalog**: Locally maintained, offline catalog of known factory-default vendor credentials used by the guarded default-credential check. Each entry associates a vendor/service with the credential(s) to try and the expected success keywords/signatures used to confirm a successful login from the response body.
- **Audit Log Entry**: A record of a security-relevant event (authentication, configuration change, run, compliance check).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of application pages, data, and actions are inaccessible without a successful sign-in.
- **SC-002**: 100% of attempts to set a password shorter than 20 characters (or otherwise violating policy) are rejected, at both account creation and password change.
- **SC-003**: An administrator can create a new Asset Discovery Profile — including target scope, port selection, discovery parameters, extracted-field selection, and host-management links — in under 5 minutes.
- **SC-004**: After a discovery run completes, an administrator can go from a result row to the correct internal host-management page for that host in a single click.
- **SC-005**: Re-requesting the same profile/scope within the configured freshness window returns results without initiating a new network scan in 100% of cases (unless "force fresh" is chosen).
- **SC-006**: Every discovery run (manual or scheduled) is retrievable from the history panel with its correct timestamp, profile, and parameters.
- **SC-007**: Scheduled profiles trigger within an acceptable tolerance of their scheduled time and produce a recorded run, with zero duplicate concurrent runs of the same profile.
- **SC-008**: The default-credential compliance check never exceeds 3 attempts per target and never waits less than 5 seconds between attempts, verifiable from the audit log across 100% of checks.
- **SC-009**: Version-validity checks complete with zero external/network lookups (fully offline), verifiable in the air-gapped environment.
- **SC-010**: Every discovered asset in a compliance-enabled run receives an unambiguous status (compliant / non-compliant / unknown / inconclusive).
- **SC-011**: An administrator can review the compliance posture of the last run of every compliance-enabled profile from the dashboard without re-scanning.
- **SC-012**: The system supports an inventory of at least 5,000 hosts and a single run covering at least a /22 subnet (~1,024 addresses), rendering results and history for that volume without perceptible degradation (history list loads in under 3 seconds).

## Assumptions

- **Authorized use**: All scanning and compliance checks target the organization's own internal infrastructure and are authorized network-administration activity; the operators are trusted administrators.
- **Air-gapped deployment**: The application and its host have no internet access. All reference data (version validity, default-credential catalog) is provisioned and updated locally/offline.
- **Designated telemetry tool**: nmap is the underlying discovery/telemetry tool and is installed on the host with sufficient privileges to perform the configured scans; the application orchestrates it rather than replacing it.
- **Single-tenant local install**: The product runs as a local web application for a small number of operators on the same trusted host/network segment.
- **Scale**: The deployment targets a medium environment — an overall inventory of up to ~5,000 hosts, with a single run covering one or more /24–/22 subnets (up to ~1,024 addresses per /22). Larger, multi-site deployments are out of scope for v1.
- **Role model**: Unless a tiered role model is later specified, every authenticated operator has full administrator capabilities (create/edit/delete profiles, run, schedule, view history). A single consistent operator role is assumed for v1.
- **Concurrency**: A few operators may use the dashboard at the same time. The system provides conflict detection for simultaneous profile edits and prevents duplicate concurrent runs, but is not required to scale to large concurrent teams.
- **Host-management pages**: Internal host-management web pages exist and are reachable from the operator's browser; the product only links to them via configured templates and does not implement them.
- **Compliance semantics**: "Default credentials in use" is treated as a non-compliant security-hygiene finding; the guarded check's purpose is detection, and its attempt/cooldown limits exist to protect target devices from lockout.
- **Scheduling granularity**: Recurring schedules are expressed at an administrator-friendly granularity (e.g., interval or calendar-based such as daily/weekly); sub-minute scheduling is out of scope for v1.
- **Out of scope for v1**: automated remediation of findings (the product detects and reports, it does not change device configurations), external IdP/SSO integration, multi-site federation, and internet-based data feeds.

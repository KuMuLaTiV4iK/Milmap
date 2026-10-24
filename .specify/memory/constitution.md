<!--
SYNC IMPACT REPORT (temporary — remove before committing the amended file)
- Version change: 1.1.0 → 2.0.0
- Bump rationale: MAJOR — Principle III (Device-Safety Invariants, NON-NEGOTIABLE) is redefined:
  the fixed "no more than 3 attempts per target" ceiling is replaced by an operator-configurable
  per-target attempt ceiling that defaults to the size of the selected credential dictionary. This
  is a backward-incompatible redefinition of a previously non-waivable numeric invariant, so it is
  MAJOR even though the rest of the principle (central enforcement, the ≥5-second cooldown, the
  standalone-tool boundary, inconclusive-on-cap) is unchanged. Authorized by the project owner for
  feature 008 (credential-tool fixes): exhaustively testing a chosen default-credential dictionary.
- Modified principles:
    III. Device-Safety Invariants — attempt cap changed from a fixed 3 to a configurable per-target
         ceiling (default = selected dictionary size); the ≥5-second cooldown remains NON-NEGOTIABLE
         and un-waivable, central enforcement is retained, and the inconclusive-on-cap rule now
         applies when an operator sets a ceiling below the dictionary size. The stop-on-match
         behavior is made explicit.
- Added principles: none.
- Modified sections: none beyond Principle III.
- Added sections: none.
- Removed sections: none.
- Note on feature 001/002 references: 001 FR-037 and 002 FR-022 previously fixed the cap at 3; under
  this amendment that value becomes the default-but-overridable ceiling. The cooldown half of those
  FRs is unchanged. Existing credential-guardrail tests that assert a hard max of 3 must be updated
  to assert the configurable ceiling and the unchanged cooldown.
- Templates/commands: constitution is read at runtime by downstream commands; no template files
  modified here.
- Follow-up TODOs: none. Ratification date unchanged (2026-10-21); last amended set to 2026-10-23.
-->

# Asset Inventory & Compliance Management Dashboard (Milmap) Constitution

## Core Principles

### I. Offline-First / Air-Gapped

The system MUST operate with zero internet access at build-time install and at runtime.

- All third-party dependencies MUST be vendored (local wheelhouse / committed static assets); no
  CDN, npm, or package-index fetches at install or runtime.
- Compliance version/firmware validity checks MUST perform ZERO external or network lookups
  (FR-034); they resolve only against locally maintained reference data.
- All reference datasets (version-validity data, default-credential catalog, NSE-script allow-list)
  MUST be local and updatable offline (FR-040).
- NSE scripts MUST execute only from the locally installed `nmap` script store — no script
  download or `--script-updatedb` network activity (002 FR-017).

**Rationale**: The product is deployed on an isolated corporate network; any hidden external
dependency would make it uninstallable or unverifiable in the target environment.

### II. Security by Default

Access is closed unless explicitly granted, and secrets are never recoverable.

- No page, data, or action is reachable without an authenticated session (FR-001).
- Passwords MUST meet policy (minimum 20 characters) at creation and change, and MUST be stored
  only as a strong one-way hash — never plaintext or recoverable form (FR-002, FR-003).
- Sign-in MUST be throttled/locked after a configurable number of consecutive failures (FR-004);
  sessions MUST expire on a configurable idle timeout (FR-005).
- Attempted credential secrets used during compliance checks MUST NOT be persisted in recoverable
  form anywhere, including logs (FR-039).

**Rationale**: The dashboard exposes the organization's full internal asset map and compliance
findings; a weak default or a leaked secret compromises the whole inventory.

### III. Device-Safety Invariants (NON-NEGOTIABLE)

Active checks against real devices MUST never risk harming those devices.

- The default-credential check MUST wait at least 5 seconds between consecutive authentication
  attempts against a target. This cooldown is NON-NEGOTIABLE and MUST NOT be shortened or waived by
  any configuration or code path (FR-037; 002 FR-022).
- The number of authentication attempts per target MUST be bounded by a ceiling. That ceiling is
  operator-configurable and defaults to the size of the selected credential dictionary (i.e. by
  default the check may try every credential in the chosen dictionary once, no more). An operator
  MAY set a lower ceiling; the system MUST NOT exceed the effective ceiling for a target
  (feature 008). The former fixed value of 3 is the historical default, not a hard limit.
- The check MUST stop attempting further credentials against a target as soon as one is accepted
  (stop-on-match); it never continues past a confirmed match.
- These limits MUST be enforced centrally (in the single credential-check orchestrator), not
  per-protocol, so every probe inherits them identically.
- The check is a standalone tool: it runs ONLY when an operator initiates it on demand or when its
  own scheduled task triggers it (002 FR-020, FR-021). It MUST NOT run as part of a discovery
  profile's run. Scheduled runs inherit the identical cooldown and ceiling — no path, manual or
  scheduled, may bypass the central guard.
- When a configured ceiling below the dictionary size prevents every credential from being tried
  and none matched, the asset MUST be flagged `inconclusive` rather than continuing to attempt
  (FR-038). When the whole dictionary is exhausted with no match, the asset is `compliant`.
- These invariants MUST be covered by dedicated tests and be observable in the audit log (SC-008;
  002 SC-006).

**Rationale**: Rapid repeated attempts can lock out production devices (phones, switches); the
≥5-second cooldown — the invariant that most directly prevents lockout — therefore remains
non-negotiable and overrides convenience or performance. The attempt ceiling is made configurable
(defaulting to the chosen dictionary's size) so an authorized operator can exhaustively audit a
specific default-credential set, while retaining the ability to cap attempts on devices known to
lock after a fixed number of failures. Central enforcement and stop-on-match keep every protocol
uniformly safe.

### IV. Auditability

Security-relevant actions MUST leave a trustworthy trail.

- The system MUST record sign-in success/failure, lockouts, profile changes, run executions,
  compliance checks, schedule changes, account/role and user-management actions, configuration
  (security-settings) changes, NSE-script allow-list changes, and standalone credential-tool checks
  to an append audit log (FR-006; 002 FR-014, FR-024, FR-029, FR-031).
- Audit records MUST include enough detail to verify the Device-Safety Invariants (attempt counts
  and timings) and MUST NOT contain secrets.

**Rationale**: An internal security tool is only trustworthy if its own actions can be reviewed
after the fact.

### V. Testable & Independently Deliverable

Work MUST be structured so value ships and is verified incrementally.

- Each user story MUST be independently testable and deliverable.
- Every functional requirement MUST have at least one task and a clear acceptance check; success
  criteria MUST be measurable.
- The CI invariant suite (auth gate, ≥20-char policy, credential guardrails, offline version check,
  no duplicate concurrent runs, optimistic-concurrency conflict detection, role-based access
  control, NSE allow-list enforcement) MUST pass before a story is considered done.

**Rationale**: Incremental, independently verifiable slices reduce risk and keep the security-
critical invariants continuously enforced.

### VI. Simplicity (YAGNI)

Prefer the simplest design that satisfies the requirements at the stated scale.

- The deployment targets a single host and ~5,000-host inventory; solutions MUST NOT introduce
  distributed components, external brokers, or services beyond this need without justification.
- A single scheduling engine MUST serve both discovery-profile schedules and standalone-tool tasks
  (002 FR-021); do not add a second scheduler.
- Localization MUST use a single-locale catalog (no heavyweight i18n framework) while one locale is
  in scope.
- Any added complexity MUST be recorded in the plan's Complexity Tracking with the simpler
  alternative it rejects and why.

**Rationale**: A self-contained, single-process deployment is easier to install, audit, and
maintain on an isolated host than a distributed system.

### VII. Least-Privilege Roles

Administrative capability MUST be separated from routine operation and granted only as needed.

- The system MUST support exactly two roles — Administrator and Operator — with no read-only viewer
  role (002 FR-027).
- Operators MAY perform all discovery work (create/edit/run/delete/schedule profiles, run the
  standalone tools, review results/history). User management, account/session security settings, and
  the NSE-script allow-list MUST be Administrator-only; attempts by Operators MUST be denied
  (002 FR-028, FR-031).
- On a fresh install the first account MUST be an Administrator; accounts created afterward default
  to Operator (002 FR-030).
- The system MUST never allow an action that leaves it with no active Administrator, and MUST never
  allow the password minimum length to be lowered below the 20-character floor at runtime
  (002 FR-032, FR-033).

**Rationale**: A single all-powerful role made every operator able to change security posture and
user accounts; separating duties limits blast radius and makes privileged actions deliberate and
auditable.

## Security & Compliance Requirements

- **Scanning authorization**: All discovery and compliance activity targets the organization's own,
  authorized internal infrastructure only.
- **Input safety**: nmap parameters MUST be restricted to a validated allow-list; raw/free-form
  flags are rejected, preventing command injection (FR-011). NSE scripts MUST be constrained to a
  curated, Administrator-editable allow-list — no free-form `--script` input; only allow-listed
  script ids ever reach the command line (002 FR-009, FR-012, FR-013). Adding a script outside
  Nmap's "safe" categories is permitted for Administrators but MUST surface a warning and be
  audit-logged; the default allow-list ships safe-category scripts only (002 FR-016, FR-018).
- **Role-gated administration**: Administrator-only functions (user management, security settings,
  allow-list) MUST be enforced server-side, not merely hidden in the UI (002 FR-028, FR-031).
- **Concurrency safety**: Profile edits MUST use optimistic concurrency (no silent overwrite,
  FR-042); the system MUST prevent duplicate concurrent runs of the same profile and of the same
  standalone-tool task across manual and scheduled triggers (FR-043; 002 FR-021).
- **Data at rest**: Credentials hashed with a memory-hard algorithm (Argon2id); reference catalogs
  and the database live under the deployment's local `data/` directory.

## Development Workflow & Quality Gates

- **Spec-driven flow**: Changes follow Spec Kit — spec → plan → tasks → implement; the constitution
  is checked at plan time and re-checked after design.
- **Quality gates before "done"**: lint/format clean; the CI invariant suite (Principle V) green;
  new/changed behavior covered by tests; no secrets in code, logs, or fixtures.
- **Review**: Any change touching authentication, roles/authorization, the credential-check
  guardrails, the NSE allow-list, or audit logging requires explicit review against Principles II,
  III, IV, and VII.
- **Offline verification**: Installability and the offline version-check invariant MUST be validated
  in (or simulating) an air-gapped environment before release.

## Governance

- This constitution supersedes other practices for this project. When guidance conflicts, the
  constitution wins; Principle III's ≥5-second cooldown and central-enforcement/stop-on-match
  guarantees are non-negotiable and cannot be waived (the attempt ceiling is operator-configurable
  per that principle).
- **Amendments** MUST be made via `/speckit-constitution`, documented in the Sync Impact Report,
  and versioned per semantic versioning:
  - MAJOR: backward-incompatible governance/principle removal or redefinition.
  - MINOR: a new principle/section or materially expanded guidance.
  - PATCH: clarifications and non-semantic refinements.
- **Compliance review**: Plans MUST include a Constitution Check gate; tasks and implementation MUST
  trace to requirements; violations MUST be justified in Complexity Tracking or resolved before
  implementation proceeds.

**Version**: 2.0.0 | **Ratified**: 2026-10-21 | **Last Amended**: 2026-10-23

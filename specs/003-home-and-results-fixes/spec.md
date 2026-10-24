# Feature Specification: Home Page & Results Corrections

**Feature Branch**: `003-home-and-results-fixes`

**Created**: 2026-10-22

**Status**: Draft

**Input**: User description: "Milmap MVP v0.2 corrections and main-page enhancements. Main user stories are #4 and #5; items #1–#3 are corrections to existing behavior."

## Clarifications

### Session 2026-10-22

- Q: When a large scan (>10 ports) finds a responding host with no open ports, should the ports cell show explanatory text or be empty? → A: Show the text "Всі порти closed або filtered" (align FR-010 and Edge Cases to US3 Scenario 4).
- Q: How is the small-vs-large scan-size threshold determined, including when a profile specifies no explicit ports? → A: Count the actual number of ports present in the scan's results/output and apply the ≤10 rule to that count (not the profile's port specification).
- Q: How many scans should the Home page recent-scans overview show, and in what order? → A: The 20 most recent scans across all profiles, ordered newest first.
- Q: Who may open the reference-versions dictionary view, and is it read-only? → A: Both Operators and Administrators may view AND manually edit the reference-versions dictionary in-app, for convenience (not read-only). Edits are audit-logged as configuration changes per Constitution Principle IV.
- Q: Should scheduling cover discovery-profile scans, given that currently only the credential/password check can be scheduled? → A: Yes — add profile-scan scheduling as a new user story (US6). A schedule is an independent recurring task that references a profile; creating/changing a schedule does NOT require editing the profile, and a profile may have multiple schedules.
- Q: Should profiles be creatable without a target, with the target supplied at launch from the Home page? → A: Yes (added to US1). A profile may be saved without a target; from the Home page the operator selects the profile and sets the target (target only — ports and other parameters stay as defined) for that run. The launch-time target is used for that run only and is not persisted back to the profile.
- Q: Can a target-less profile be scheduled, and where does the target come from? → A: Each profile-scan schedule carries its OWN target, set when the schedule is created (defaulting to the profile's saved target if it has one) and used for every run of that schedule; the target is stored on the schedule, so both target-less and targeted profiles are schedulable. Additionally, a recurring schedule can be created directly from a past scan in the run history, prefilling the profile, target, and parameters from that run.
- Q: When a target-less profile is launched from the regular profiles list (not Home), what happens? → A: It prompts for a target there too, identically to the Home-page launch (same ephemeral, per-run behavior); the profiles-list "Run" is never a dead end for target-less profiles.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Useful Home page with recent profiles and all recent scans (Priority: P1)

An administrator or operator signs in and lands on the main page. Instead of a
compliance-only panel that is empty whenever no profile has version evaluation
enabled, they see a genuinely useful "Home" (Головна) page with two things:
their most recently touched discovery profiles, each launchable directly from
there; and an overview of recent scans across ALL profiles — not only profiles
that have version evaluation enabled. Where a scan did evaluate compliance, its
compliance posture is shown too, but a scan without version evaluation still
appears. Profiles can also be saved without a target and used as reusable
templates: the operator picks such a profile on the Home page and supplies the
target there (target only — the profile's ports and other parameters are left
unchanged) to launch a run.

**Why this priority**: This is the first screen every user sees after login; its
current emptiness (screenshot 3) makes the product feel broken, and it currently
hides every scan that did not run version evaluation. Making the landing page
show all recent activity and be immediately actionable is the highest-value
change in this batch.

**Independent Test**: Sign in with at least one profile that has NO version
evaluation enabled and at least one completed scan from it; confirm the Home
page shows that scan in the recent-scans overview and shows that profile among
the recent profiles with a "Run" action, and confirm launching it from the Home
page starts a run. Delivers value even if no other story ships.

**Acceptance Scenarios**:

1. **Given** one or more discovery profiles exist and none has version
   evaluation enabled, **When** the user opens the main page, **Then** the page
   is NOT empty — it lists the 5 most recently updated profiles.
2. **Given** completed scans exist from profiles WITHOUT version evaluation
   enabled, **When** the user opens the main page, **Then** those scans appear in
   the recent-scans overview (the overview covers all scans, not only
   compliance-enabled ones).
3. **Given** the user is on the Home page, **When** they activate "Run" on a
   listed recent profile, **Then** a discovery run for that profile starts and
   the user is taken to that run's detail view (same behavior as launching from
   the profiles list).
4. **Given** more than 5 profiles exist, **When** the Home page renders the
   recent-profiles list, **Then** at most 5 are shown, ordered most-recent first.
5. **Given** a scan DID evaluate compliance, **When** it appears in the
   recent-scans overview, **Then** its compliance posture (compliant /
   non-compliant / unknown counts) is shown alongside it; **Given** a scan did
   NOT evaluate compliance, **Then** it still appears, with compliance shown as
   not-applicable rather than the scan being hidden.
6. **Given** the page is rendered, **When** the user reads the main heading and
   navigation label, **Then** both read "Головна" (Home), not "Панель
   відповідності".
7. **Given** a discovery profile was saved without a target, **When** the user
   selects it on the Home page and chooses to run it, **Then** the user is
   prompted to supply a target and the run starts with that target while the
   profile's ports and other parameters are used unchanged.
8. **Given** the user supplies a launch-time target for a target-less profile,
   **When** the run completes, **Then** the target was used for that run only and
   the profile remains target-less (the supplied target is not persisted back to
   the profile).

---

### User Story 2 - Dynamic UI that updates without manual page reloads (Priority: P2)

The application behaves like a dynamic web application: when a user performs an
action that changes what a list or view should show, that view updates on its
own, without the user manually reloading the browser. Duplicating or deleting a
profile is the concrete example from testing — the profiles list must update
itself — but the requirement is the general principle, applied consistently to
the views where a user action changes the displayed data (profile
create/edit/duplicate/delete, and other in-page lists that reflect a mutation
the user just made).

**Why this priority**: Manual-refresh-to-see-changes makes the product feel
static and untrustworthy and causes duplicate/accidental actions. It is a
cross-cutting UX principle, but a smaller surface than the Home page redesign.

**Independent Test**: From the profiles list, duplicate a profile and confirm the
new copy appears without a manual page reload; delete a profile and confirm its
row disappears without a manual reload; create/edit a profile and return to the
list to find it already reflects the change.

**Acceptance Scenarios**:

1. **Given** the profiles list is open, **When** the user duplicates a profile,
   **Then** the duplicate appears in the list without the user manually
   reloading the page.
2. **Given** the profiles list is open, **When** the user confirms deletion of a
   profile, **Then** that profile's row is removed from the list without the
   user manually reloading the page.
3. **Given** the user creates or edits a profile, **When** the operation
   succeeds, **Then** the affected list/view reflects the change without a manual
   reload.
4. **Given** a mutating action fails, **When** the server rejects it, **Then** the
   displayed view is left consistent with server state and the user sees an error
   indication rather than a silently stale or wrongly-updated view.
5. **Given** any in-page list that is updated after a user-initiated mutation,
   **When** the mutation succeeds, **Then** the update is applied without
   requiring a full-page manual refresh (the general dynamic-UI principle, of
   which the profiles list is one instance).

---

### User Story 3 - Port column adapts to how many ports were scanned (Priority: P3)

An operator reviews a completed run's results table. How the ports column is
presented depends on how many ports the scan targeted:

- For a **small scan (10 or fewer ports)**, the operator sees the status of EACH
  scanned port for every responding host (e.g. 22/tcp open, 8291/tcp filtered) —
  the full per-port picture is useful and compact.
- For a **large scan (more than 10 ports)**, the operator sees ONLY the ports
  that came back open — showing every filtered/closed port would be noise.

Either way, the column never shows a filtered/closed port as if it were open
(the current defect in screenshots 2 and 4).

**Why this priority**: A correctness defect that actively misleads — the current
table shows closed/filtered ports as if open, undermining the inventory's
trustworthiness. The small-scan per-port status view also recovers useful
diagnostic detail. It is a correction/refinement, not new capability.

**Independent Test**: Run a small scan (≤10 ports) against the provided sample
output (`1_prof_output.txt`, 2 ports scanned) where host 192.168.1.1 has port 22
open and 8291 filtered; confirm the host's row shows both 22 as open and 8291 as
filtered with their statuses. Separately run a large scan (>10 ports) and confirm
each host's row lists only open ports.

**Acceptance Scenarios**:

1. **Given** a scan targeting 10 or fewer ports, **When** the operator views a
   responding host's row, **Then** every scanned port is shown with its state
   (open / filtered / closed), not only the open ones.
2. **Given** a scan targeting more than 10 ports, **When** the operator views a
   responding host's row, **Then** only the ports with state "open" are listed;
   filtered and closed ports are omitted.
3. **Given** either scan size, **When** a port is filtered or closed, **Then** it
   is never presented as if it were open.
4. **Given** a large scan where a responding host has no open ports, **When** the
   operator views that host's row, **Then** the ports cell shows text "Всі порти closed або filtered" and the host still appears because it responded
   (is "up").
5. **Given** the detected service version is taken from a port, **When** the
   version is shown, **Then** it is derived from an open port's service, not a
   filtered/closed one.

---

### User Story 4 - Non-compliant versions show the expected valid version (Priority: P3)

An operator sees a host flagged as non-compliant for its service version.
Instead of only a "non_compliant" label, the row shows the expected valid
version from the local reference dataset and is highlighted in orange so it
stands out. The maintained dictionary of reference versions the evaluation uses
is reviewable within the application.

**Why this priority**: Turns a bare verdict into an actionable finding (what to
upgrade to), and the orange cue speeds triage. A correction/enhancement to an
existing check rather than a new check.

**Independent Test**: With the local reference dataset listing OpenSSH 7.x as
invalid and 9.x as valid, run a scan detecting OpenSSH 7.4; confirm the row is
highlighted orange, shows the non-compliant status, and surfaces the expected
valid version ("upgrade to 9.x" / the compliant reference entry). Separately,
confirm the reference versions dictionary is viewable in the app.

**Acceptance Scenarios**:

1. **Given** a host whose detected version matches an "invalid" reference entry,
   **When** its results row renders, **Then** the row is visually highlighted in
   orange.
2. **Given** such a non-compliant host, **When** the operator reads the
   compliance cell, **Then** it shows the expected valid version / remediation
   guidance drawn from the local reference dataset (e.g. the note or the
   matching "valid" entry for the same product), not just the word
   "non_compliant".
3. **Given** a host whose version is compliant or unknown, **When** its row
   renders, **Then** it is NOT orange-highlighted.
4. **Given** the operator wants to audit the evaluation basis, **When** they open
   the reference-versions view in the application, **Then** they can see the
   maintained list of reference version entries (product, version match,
   valid/invalid status, note).

---

### User Story 5 - NSE scripts selectable from a list control (Priority: P4)

When editing a profile, an operator selects NSE scripts from a drop-down /
multi-select list of allow-listed scripts rather than the current layout.

**Why this priority**: A usability refinement to an already-working feature;
lowest priority and smallest blast radius. The underlying allow-list, selection
persistence, and command composition already work and must not regress.

**Independent Test**: Open a profile editor, confirm allow-listed NSE scripts are
offered through a list/drop-down control, select one or more, save, reopen, and
confirm the same scripts are still selected and included in the command preview.

**Acceptance Scenarios**:

1. **Given** the allow-list contains enabled scripts, **When** the operator opens
   the NSE-scripts control in the profile editor, **Then** those scripts are
   presented as a selectable list / drop-down.
2. **Given** the operator selects one or more scripts and saves, **When** they
   reopen the profile, **Then** exactly those scripts are shown as selected.
3. **Given** a script was previously selected but later removed/disabled on the
   allow-list, **When** the operator opens the editor, **Then** the stale
   selection does not silently pass validation on save (consistent with existing
   allow-list enforcement).

---

### User Story 6 - Schedule discovery-profile scans (Priority: P2)

Today an operator can create a recurring schedule only for the
credential/password check (the standalone tool). They want the same for
discovery: schedule a profile's scan to run automatically on a recurring
schedule. A schedule is an independent, recurring task that references a
profile — so the operator can add, change, or remove a schedule without editing
the profile itself, and a single profile can have one or more schedules.

**Why this priority**: Automated recurring discovery is a core advertised
capability that is currently missing for profiles; without it the inventory
only updates when someone runs a scan by hand. It is a meaningful capability
gap, but behind the Home-page fix in immediate visible value.

**Independent Test**: Create a recurring schedule that references an existing
discovery profile (supplying the schedule's target) without editing the profile;
confirm the profile's scan runs automatically against that target when the
schedule fires, the run is stored in history like a manual run, and the schedule
can be edited or removed independently of the profile. Separately, from a past
scan in the run history, create a recurring schedule and confirm it reuses that
run's profile and target.

**Acceptance Scenarios**:

1. **Given** an existing discovery profile, **When** the operator creates a
   recurring scheduled task referencing that profile, **Then** the task is saved
   and the profile's scan runs automatically on that schedule, without the
   operator having to edit the profile.
2. **Given** a profile with a profile-scan schedule, **When** the operator edits
   or removes that schedule, **Then** the change applies to the schedule alone
   and the profile definition is unchanged.
3. **Given** a profile may need to run on more than one cadence, **When** the
   operator defines multiple schedules for the same profile, **Then** each
   schedule is honored independently.
4. **Given** a scheduled profile run is about to start while a run of the same
   profile is already in progress, **When** the scheduler fires, **Then** the
   existing no-duplicate-concurrent-run handling applies (no second concurrent
   run of the same profile), identical to manual launches.
5. **Given** a scheduled profile run executes, **When** it completes, **Then** it
   is recorded in run history and the audit log exactly as a manual run is.
6. **Given** a target-less profile (or any profile), **When** the operator
   creates a schedule and supplies the schedule's target, **Then** every run of
   that schedule uses that stored target without modifying the profile, and a
   later change to the profile's saved target does not alter the schedule.
7. **Given** a completed scan in the run history, **When** the operator chooses
   to schedule it, **Then** a recurring schedule is created reusing that scan's
   profile, target, and scan parameters.

---

### Edge Cases

- **No profiles at all**: The Home page recent-profiles section shows an empty
  state message, not an error.
- **No scans yet**: The Home page recent-scans overview shows an empty state
  message, not an error.
- **Profile never run**: A recent profile with no runs still appears in the
  recent list and is runnable.
- **Exactly 10 ports scanned**: Treated as a small scan — per-port statuses are
  shown (the small-scan threshold is "10 or fewer").
- **Small scan, host up but all ports filtered/closed**: The host's row shows
  each scanned port with its filtered/closed status (not an empty cell).
- **Large scan, host up but no open ports**: The host's row shows the text
  "Всі порти closed або filtered" in the ports cell and the host still appears
  (US3 scenario 4).
- **Non-compliant product with no matching "valid" reference entry**: The row is
  still orange and shows whatever remediation note the invalid entry carries,
  without inventing a valid version.
- **Concurrent/ already-running profile launched from Home**: Launching a profile
  already running surfaces the same "already running" handling as the profiles
  list, not a crash.
- **Mutation that another session already applied**: A dynamic-UI update
  tolerates server state that already reflects (or already removed) the target,
  without breaking the view.
- **Target-less profile run without a target**: Launching a target-less profile
  from Home without supplying a target is blocked with a prompt/validation
  message, not a crash or an empty-target scan.
- **Invalid launch-time target**: A supplied launch target that fails target
  validation is rejected the same way an invalid profile target is, and no run
  starts.
- **Scheduled run collides with a manual run**: A scheduled profile run that
  would duplicate an in-progress run of the same profile is suppressed by the
  existing no-duplicate-concurrent-run handling.
- **Profile with schedules is deleted**: Deleting a profile removes or disables
  its profile-scan schedules so no orphaned schedule fires against a missing
  profile.
- **Schedule created with an invalid/empty target**: The schedule is rejected by
  the same target validation as a profile target; it cannot be saved or run with
  an invalid or empty target.
- **Schedule from history of a since-changed profile**: Scheduling from a past
  scan copies that run's target and parameters onto the new schedule; later edits
  to the profile do not retroactively change the schedule's stored target.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The main page MUST be titled and labeled "Головна" (Home) in both
  the page heading and the navigation, replacing "Панель відповідності".
- **FR-002**: The main page MUST display the 5 most recently updated discovery
  profiles, ordered most-recent first, regardless of whether any profile has
  version/compliance evaluation enabled.
- **FR-003**: Each recent profile on the main page MUST offer a direct "Run now"
  action that starts a discovery run and behaves identically to launching the
  profile from the profiles list.
- **FR-003a**: A discovery profile MUST be creatable and savable WITHOUT a target
  (target is optional at profile definition time).
- **FR-003b**: When the operator launches a target-less profile from the Home
  page OR from the profiles list, the system MUST prompt for a target and start
  the run using that target together with the profile's existing ports and other
  parameters (only the target is set at launch; ports/parameters are not
  changed). The profiles-list launch of a target-less profile MUST NOT be a dead
  end.
- **FR-003c**: A target supplied at launch for a target-less profile MUST be used
  for that run only and MUST NOT be persisted back to the profile; the profile
  remains target-less afterward.
- **FR-003d**: A target supplied at launch MUST pass the same target validation
  as a target saved on a profile (no bypass of existing target validation).
- **FR-004**: The main page MUST remain non-empty when profiles exist but none
  has compliance evaluation enabled (i.e. page usefulness MUST NOT depend on
  compliance being configured).
- **FR-005**: The main page MUST present a recent-scans overview covering scans
  from ALL profiles, regardless of whether version/compliance evaluation was
  enabled; scans without compliance evaluation MUST still appear. The overview
  MUST show the 20 most recent scans, ordered most-recent first.
- **FR-005a**: For scans that did evaluate compliance, the recent-scans overview
  MUST show their compliance posture; for scans that did not, it MUST indicate
  compliance is not applicable rather than omitting the scan.
- **FR-006**: After a user-initiated mutation that changes a displayed list or
  view (e.g. profile create/edit/duplicate/delete), the affected view MUST update
  to reflect the change without a manual browser reload.
- **FR-007**: Duplicating or deleting a profile from the profiles list MUST
  update the list in place without a manual browser reload (a concrete instance
  of FR-006).
- **FR-008**: A failed mutating action MUST leave the displayed view consistent
  with server state and indicate the failure to the user, rather than showing a
  silently stale or wrongly-updated view.
- **FR-009**: For a scan whose results contain 10 or fewer ports, each responding
  host's ports cell MUST show every scanned port with its state (open / filtered
  / closed). The scan-size count is the actual number of ports present in the
  scan's results/output, not the profile's port specification.
- **FR-009a**: For a scan whose results contain more than 10 ports, each
  responding host's ports cell MUST show only ports with state "open", excluding
  filtered and closed ports.
- **FR-009b**: In no case MUST a filtered or closed port be presented as if it
  were open.
- **FR-010**: In a large scan (>10 ports), a responding host with no open ports
  MUST still appear in the results table, with the ports cell showing the text
  "Всі порти closed або filtered" (not an empty cell).
- **FR-011**: The service-version value shown for a host MUST be derived from an
  open port, not from a filtered/closed port.
- **FR-012**: When a host's version is evaluated non-compliant, its results row
  MUST be visually highlighted in orange.
- **FR-013**: A non-compliant row MUST surface the expected valid version /
  remediation guidance from the local reference dataset, in addition to the
  non-compliant status.
- **FR-014**: Rows that are compliant or unknown MUST NOT receive the orange
  non-compliant highlight.
- **FR-015**: The application MUST provide a view of the maintained reference
  version dictionary (product, version match, valid/invalid status, note) used
  by the version-validity evaluation.
- **FR-015a**: Both Operators and Administrators MUST be able to manually edit
  reference-version entries (add / edit / remove) directly in that view, for
  convenience; edits take effect for subsequent version-validity evaluations.
- **FR-015b**: Each manual edit to the reference-version dictionary MUST be
  recorded to the audit log as a configuration change (Constitution Principle
  IV); no secrets are involved.
- **FR-016**: The profile editor MUST present allow-listed NSE scripts through a
  list / drop-down selection control.
- **FR-017**: NSE script selections MUST persist across save/reopen and continue
  to be reflected in the command preview, with existing allow-list enforcement
  unchanged.
- **FR-018**: No already-working behavior outside the scope of these corrections
  (authentication, RBAC, credential tool, audit logging, caching, retention) may
  be altered. The scheduling engine is extended (FR-020–FR-022) to cover
  profile-scan schedules; existing credential/password-check scheduling MUST
  continue to work unchanged.
- **FR-019**: No new runtime dependency may be introduced; the feature operates
  within the existing air-gapped stack.
- **FR-020**: The scheduling engine MUST allow creating recurring scheduled tasks
  that run a discovery profile's scan, not only the credential/password check.
- **FR-021**: A profile-scan schedule MUST be an independent task that references
  a profile; creating, editing, or removing a schedule MUST NOT require editing
  the referenced profile, and a single profile MAY have multiple independent
  schedules.
- **FR-021a**: Each profile-scan schedule MUST carry its own target, set when the
  schedule is created (defaulting to the profile's saved target when it has one);
  that stored target is used for every run of the schedule. Because the target
  lives on the schedule, a target-less profile MUST be schedulable, and a later
  change to the profile's saved target MUST NOT alter an existing schedule's
  target.
- **FR-021b**: A schedule's target MUST pass the same target validation as a
  profile target; a schedule MUST NOT be created or run with an invalid or empty
  target.
- **FR-022**: Profile-scan schedules MUST be served by the single existing
  scheduling engine (no second scheduler, per Constitution Principle VI), and
  scheduled profile runs MUST honor the same no-duplicate-concurrent-run rule and
  be recorded in run history and the audit log identically to manual runs.
- **FR-023**: The run history MUST offer an action to create a recurring
  profile-scan schedule from a past scan, prefilling the new schedule's profile,
  target, and scan parameters from that historical run.

### Key Entities *(include if feature involves data)*

- **Discovery Profile**: Existing entity; the Home page reads its name, target,
  ports, schedule flag, and last-updated ordering for the recent list. "Most
  recently updated" relies on an existing update/creation timestamp. The target
  field becomes optional (a profile may be saved with no target).
- **Scheduled Task**: Existing entity (currently used for the credential/password
  check); now also able to reference a discovery profile so the profile's scan
  runs on a recurring schedule. A schedule references a profile rather than being
  embedded in the profile, so it is managed independently and a profile may have
  several. Each profile-scan schedule additionally stores its own target (and the
  scan parameters when created from a historical run), independent of the
  profile's saved target.
- **Discovery Run / Discovered Asset / Compliance Finding**: Existing entities;
  the Home recent-scans overview and the results-table corrections (per-port
  status vs open-only depending on scan size, orange non-compliant rows, expected
  valid version) read from these. Per-port status for small scans requires each
  scanned port's state to be available to the results view (the parser already
  reads port state); whether an additional field/representation is needed is a
  planning detail, not a new user-facing entity.
- **Reference Version Entry**: Existing locally-maintained reference data
  (product, version match, valid/invalid status, note); now also surfaced in a
  read view and used to present the expected valid version on non-compliant
  rows.
- **NSE Script Allow-list Entry**: Existing entity; drives the profile editor's
  script selection control.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With at least one profile and zero compliance-enabled profiles, the
  Home page shows at least one actionable item (recent profile) in 100% of cases
  — it is never empty when profiles exist.
- **SC-002**: A user can start a discovery run directly from the Home page in a
  single action, without visiting the profiles list first.
- **SC-002a**: The Home recent-scans overview shows 100% of recent completed
  scans regardless of compliance configuration — a scan with no version
  evaluation is never hidden.
- **SC-003**: After a user-initiated mutation (duplicate, delete, create, edit),
  the affected view reflects the change with no manual page reload in 100% of
  successful operations.
- **SC-004**: For the provided sample scan (2 ports scanned → small scan), every
  host row shows both scanned ports with their correct states (22 open, 8291
  filtered on 192.168.1.1); for a large scan (>10 ports) every host row shows
  only open ports (0 filtered/closed shown).
- **SC-005**: 100% of non-compliant version rows are orange-highlighted and show
  an expected valid version / remediation note; 0% of compliant or unknown rows
  are orange-highlighted.
- **SC-006**: The maintained reference version list is both viewable and
  editable in the application by Operators and Administrators without editing a
  file on disk, and each edit appears in the audit log.
- **SC-007**: NSE script selections made through the list control survive
  save/reopen with 100% fidelity and no regression in command composition.
- **SC-008**: No regression in the existing automated test suite; all previously
  passing tests continue to pass.
- **SC-009**: An operator can schedule a discovery profile's scan to run on a
  recurring schedule without editing the profile — supplying the schedule's own
  target (so target-less profiles are schedulable) — and a scheduled run executes
  automatically against that target and is stored in history like a manual run,
  in 100% of cases.
- **SC-011**: An operator can create a recurring schedule directly from a past
  scan in the run history, and the new schedule reuses that run's profile and
  target in a single flow.
- **SC-010**: A profile can be saved with no target, and launching it from the
  Home page with a supplied target starts a run using that target and the
  profile's unchanged ports/parameters in a single flow, with the target not
  persisted back to the profile.

## Assumptions

- "Most recently updated" ordering for recent profiles uses an existing profile
  timestamp (updated-at, falling back to created-at); no new ordering field is
  introduced.
- "Recent profiles" are not per-user-scoped beyond existing visibility rules;
  all signed-in users see the same set of profiles (consistent with the current
  single-tenant, two-role model where profiles are shared).
- The reference-versions view is editable in-app by both Operators and
  Administrators (manual add/edit/remove), for convenience; offline/provisioning
  updates remain possible but are no longer the only path. In-app edits are
  audit-logged as configuration changes.
- "Orange" is realized via the existing dark SOC theme's styling tokens; no new
  color system is introduced.
- The small-vs-large scan threshold is a count of ports: "10 or fewer" is small
  (show per-port status), "more than 10" is large (show open only). The count is
  the actual number of ports present in the scan's results/output for that run,
  not the profile's port specification; this well-defines the branch even when a
  profile specifies no explicit ports (nmap default set).
- The dynamic-UI behavior (updating views without manual reload) is achieved with
  the stack's existing client-side/HTMX mechanisms already in use elsewhere; no
  new runtime dependency is added. It applies to in-page lists updated after a
  user-initiated mutation, not to passive live-streaming of changes other
  sessions make.
- The NSE list/drop-down control replaces presentation only; the allow-list
  source, persistence, validation, and command composition are unchanged.
- The orange highlight and expected-valid-version display apply to the
  version-validity control; the default-credential tool remains decoupled
  (feature 002) and is out of scope here.
- Profile-scan scheduling reuses the single existing scheduling engine that
  already runs the credential/password-check task (Constitution Principle VI); no
  second scheduler is introduced. A schedule references a profile by identity, so
  it survives profile edits and is managed separately from the profile. Each
  schedule stores its own target (unlike the interactive Home launch, whose
  target is ephemeral), which is why a target-less profile can still be scheduled.
- Scheduling from the run history is a convenience that copies an existing run's
  profile, target, and parameters onto a new schedule; it does not retroactively
  link the schedule to future changes of that profile's saved target.
- A launch-time target for a target-less profile is ephemeral (used for that run
  only) and is validated with the same target validation as a saved profile
  target; only the target is settable at launch, not ports or other scan
  parameters.

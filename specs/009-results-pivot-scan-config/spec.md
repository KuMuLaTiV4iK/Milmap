# Feature Specification: Scan-Result Host Pivot & Run Configuration Window

**Feature Branch**: `009-results-pivot-scan-config`

**Created**: 2026-10-24

**Status**: Draft

**Input**: User description: "1. Pivot workflow — 1.1 choose hosts by checkbox from the scan result tab to automatically add them to another scan with a profile or a cred check; 1.2 auto-choose hosts that have an invalid version (not unknown). Cred check is a normal action (own network, few hosts). 2. Change scan start configuration — 2.1 when running a profile without a saved target from the main tab, replace the plain browser prompt with a profile Scan configuration window similar to the profile edit tab but with a Start Scan button."

## Clarifications

### Session 2026-10-24

- Q: When "Select invalid-version hosts" runs and some rows are already manually ticked, what happens to the existing selection? → A: Add to current (union) — invalid-version rows are added to whatever is already selected; nothing already ticked is un-ticked.
- Q: Besides target, ports, timing, and extracted fields, which saved-profile settings should the one-off Scan Configuration window also let you adjust? → A: Only those four fields — the version-validity compliance toggle and the NSE script selection are inherited (read-only) from the saved profile for that run.
- Q: When a pivot is launched from the results table (scan config or credential check), how should the pre-filled form appear? → A: Navigate to the tool page with the target pre-filled (the results view is left behind; browser Back returns to it).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Review-driven Scan Configuration window (Priority: P1)

An administrator or operator starts a discovery run from the home dashboard or the profiles list. Instead of either launching blindly or being asked for a target through a bare browser prompt, they get a **Scan Configuration window** pre-filled from the chosen profile. They can review and adjust the run's target, ports, scan timing, and which telemetry fields to extract — with a live preview of the resulting scan command — and then press **Start Scan**. The adjustments apply only to that single run; the saved profile is untouched.

**Why this priority**: This replaces the current jarring `window.prompt` and is the shared foundation the scan-pivot flow (User Story 3) builds on. It delivers standalone value immediately — a usable, reviewable launch step for every run.

**Independent Test**: With no other story implemented, click **Run now** on a profile that has a saved target and confirm the configuration window opens pre-filled and launches on **Start Scan**; repeat on a target-less profile and confirm Start Scan is blocked until a target is entered. Verify the saved profile is unchanged afterward.

**Acceptance Scenarios**:

1. **Given** a profile with a saved target, **When** the operator clicks **Run now**, **Then** the Scan Configuration window opens pre-filled with that profile's target, ports, timing, and extracted-field selections, and the command preview reflects them.
2. **Given** the configuration window is open, **When** the operator changes the timing and removes a port from the range and clicks **Start Scan**, **Then** a run is launched using the shown values and the saved profile's stored settings remain unchanged.
3. **Given** a target-less profile, **When** its configuration window opens, **Then** the target field is empty and **Start Scan** is disabled (with a clear prompt) until at least one valid target is entered.
4. **Given** the window is open, **When** the operator enters an invalid target or port specification, **Then** the launch is rejected with a field-level message and no run starts.
5. **Given** any **Run now** entry point (home dashboard, profiles list), **When** the operator triggers a run, **Then** the legacy browser prompt for a target never appears.

---

### User Story 2 - Select hosts and run a credential check (Priority: P1)

After a discovery run completes, the operator is looking at the results table and spots a handful of hosts worth checking for factory-default credentials. They tick the checkboxes next to those hosts and choose **Check credentials on selected**. The standalone credential tool opens with those hosts' addresses already filled in as the target scope; the operator picks the port, service, and credential dictionary and starts the check. No host address is retyped.

**Why this priority**: This is the headline pivot the user asked for and is independently valuable — it turns "I found something" into "I'm checking it" without re-entering targets. It is independent of the scan-configuration window because it routes into the existing credential tool.

**Independent Test**: On a completed run's results page, select two or more host rows, invoke **Check credentials on selected**, and confirm the credential tool opens with exactly those addresses pre-filled as the target scope and runs under the standard guardrails once a port/service/dictionary are chosen.

**Acceptance Scenarios**:

1. **Given** a completed run's results table, **When** the operator ticks two host checkboxes and chooses **Check credentials on selected**, **Then** the credential tool's run form is pre-filled with exactly those two addresses as the target scope.
2. **Given** the pre-filled credential tool, **When** the operator selects a port, service, and dictionary and starts the check, **Then** the check runs against the selected hosts honoring the ≥5-second cooldown, the configurable attempt ceiling (default = dictionary size), and stop-on-match.
3. **Given** a credential check started from this pivot, **When** it runs, **Then** the action is recorded in the audit log like any other credential-tool run, with no secrets stored.
4. **Given** no host checkboxes are ticked, **When** the operator looks at the results toolbar, **Then** the **Check credentials on selected** action is disabled.

---

### User Story 3 - Select hosts and run another scan against them (Priority: P1)

From the same results table, the operator wants to run a *different* discovery profile (for example a deeper SSH-version profile) against just the hosts they picked. They tick the relevant checkboxes, choose **Scan selected with profile…**, and pick a profile. The Scan Configuration window from User Story 1 opens with the selected hosts already filled in as the target, so the operator can review, adjust if needed, and press **Start Scan**. The run targets exactly those hosts and does not alter the chosen profile.

**Why this priority**: The second half of the pivot ask; completes the "drill-down into a subset" workflow. It reuses the User Story 1 window (confirming selected hosts as the target), so it is best delivered alongside or just after that story.

**Independent Test**: On a completed run's results page, select host rows, invoke **Scan selected with profile…**, pick a profile, and confirm the Scan Configuration window opens with those hosts as the target; on **Start Scan** confirm a new run is created targeting exactly those hosts while the chosen profile's saved target is unchanged.

**Acceptance Scenarios**:

1. **Given** selected host rows, **When** the operator chooses **Scan selected with profile…** and picks a profile, **Then** the Scan Configuration window opens pre-filled with the selected host addresses as the target and that profile's other settings.
2. **Given** that window, **When** the operator clicks **Start Scan**, **Then** a new run is launched targeting exactly the hosts shown, and the chosen profile's saved target scope is not modified.
3. **Given** the operator adjusts the target in the window before starting (adds or removes a host), **When** they click **Start Scan**, **Then** the run uses the final shown list, not the original selection.
4. **Given** a profile already has a run in progress, **When** the operator tries to launch another run of the same profile, **Then** the duplicate concurrent run is prevented with a clear message.

---

### User Story 4 - Auto-select hosts with an invalid version (Priority: P2)

Rather than hunting through a long results table for every host flagged with a bad firmware/software version, the operator clicks **Select invalid-version hosts**. The system ticks exactly the rows whose version-validity check came back *non-compliant* (invalid), and leaves untouched the rows that are compliant or whose version could not be determined (unknown). From there the operator pivots those hosts into a scan or a credential check as in the other stories.

**Why this priority**: A convenience accelerator on top of the selection mechanism. Valuable but not required for the core pivot to work, so it ships after the manual selection is in place.

**Independent Test**: On a run that was evaluated for version compliance and contains a mix of compliant, non-compliant, and unknown hosts, click **Select invalid-version hosts** and confirm only the non-compliant rows become selected.

**Acceptance Scenarios**:

1. **Given** a run evaluated for version validity with compliant, non-compliant, and unknown hosts, **When** the operator clicks **Select invalid-version hosts**, **Then** exactly the non-compliant rows are selected and compliant and unknown rows are not.
2. **Given** a run where version compliance was not evaluated, **When** the operator looks at the toolbar, **Then** **Select invalid-version hosts** is disabled with a short explanation.
3. **Given** some rows are already manually selected, **When** the operator clicks **Select invalid-version hosts**, **Then** the invalid-version rows are added to the existing selection (union — no already-selected row is un-ticked) and the selection count updates.

---

### Edge Cases

- **Nothing selected**: pivot actions (**Scan selected with profile…**, **Check credentials on selected**) are disabled until at least one host is selected.
- **Run not evaluated for version**: **Select invalid-version hosts** is disabled with an explanation; manual selection still works.
- **Duplicate / overlapping addresses**: selected addresses are de-duplicated before becoming a target; a host that also falls within a profile's saved range is not added twice.
- **Empty target on launch**: a target-less profile (or a cleared target field) blocks **Start Scan** with a message; no run starts.
- **Invalid input in the window**: target or port values outside the validated allow-list are rejected inline; raw/free-form scan flags are never accepted (input-safety invariant).
- **Duplicate concurrent run**: launching a profile that already has a run in progress is prevented, whether launched from Run now or from the scan pivot.
- **Large selection**: selecting many hosts (e.g., hundreds) still produces a single valid target list and a single launch.
- **Cancelled/failed/running source run**: selection and pivot operate on the host rows present; pivoting does not depend on the source run still running.
- **Credential check with unknown port/service**: the operator must still choose a port, service, and dictionary in the credential tool; these are not auto-inferred per host by this feature.

## Requirements *(mandatory)*

### Functional Requirements

#### Host selection on scan results

- **FR-001**: The scan results view MUST present a selection control (checkbox) on each host row, plus a way to select all visible hosts and clear the selection.
- **FR-002**: The results view MUST display the current number of selected hosts and MUST enable the pivot actions only while at least one host is selected.
- **FR-003**: The system MUST provide a **Select invalid-version hosts** action that selects the hosts whose version-validity result is non-compliant, excluding hosts that are compliant and hosts whose version is unknown. When hosts are already manually selected, this action MUST add the invalid-version hosts to the existing selection (union) without un-selecting any already-selected host.
- **FR-004**: The **Select invalid-version hosts** action MUST be unavailable (and explain why) when the source run was not evaluated for version validity.
- **FR-005**: Host selection MUST be scoped to a single run's results view and MAY be ephemeral (it need not persist across page reloads).

#### Pivot to a credential check

- **FR-006**: From the selected hosts, the operator MUST be able to initiate a credential check that navigates to the standalone credential-tool page pre-filled with the selected host addresses as its target scope (the results view is left behind; browser Back returns to it).
- **FR-007**: Credential checks launched via this pivot MUST run under the central device-safety guardrails unchanged — the ≥5-second cooldown (non-negotiable), the operator-configurable attempt ceiling (default = selected dictionary size), and stop-on-match — with no bypass path.
- **FR-008**: The operator MUST still choose the port, service, and credential dictionary for the check; this feature does not infer them per host.
- **FR-009**: Credential checks launched via this pivot MUST be recorded in the audit log like any credential-tool run, and MUST NOT persist any attempted secret in recoverable form.

#### Pivot to another scan

- **FR-010**: From the selected hosts, the operator MUST be able to choose a discovery profile and launch a new run against those hosts.
- **FR-011**: Choosing **Scan selected with profile…** MUST navigate to the Scan Configuration page (the same window used by Run now) pre-filled with the selected host addresses as the target and the chosen profile's other settings, for review and adjustment before launch (the results view is left behind; browser Back returns to it).
- **FR-012**: The launched run MUST target exactly the host list shown in the window at the moment of **Start Scan**, de-duplicated, and MUST NOT modify the chosen profile's saved target or other stored settings.

#### Scan Configuration window (launch step)

- **FR-013**: Clicking **Run now** for any profile (home dashboard and profiles list) MUST open a Scan Configuration window instead of the legacy browser prompt; the browser prompt for target entry MUST be removed from all Run now entry points.
- **FR-014**: The Scan Configuration window MUST be pre-filled from the selected profile's current settings and MUST allow editing, for this run only, of exactly these four fields: target scope, port specification, scan timing, and the selection of extracted telemetry fields. The version-validity compliance toggle and the NSE script selection MUST be inherited from the saved profile and applied to the run as saved (shown for context but not editable in this window).
- **FR-015**: The window MUST show a live preview of the scan command that the shown settings would produce, consistent with the profile editor's preview.
- **FR-016**: The window MUST provide a **Start Scan** action that launches a run using the shown settings; for a target-less profile (or a cleared target), **Start Scan** MUST be blocked until at least one valid target is provided.
- **FR-017**: Adjustments made in the window MUST apply only to the launched run and MUST NOT persist to the saved profile (saving profile changes remains a profile-editor action).
- **FR-018**: Target, port, timing, and extracted-field inputs in the window MUST be validated against the same rules as the profile editor, including the scan-parameter allow-list; raw/free-form scan flags MUST be rejected.

#### Cross-cutting

- **FR-019**: Launching a run from either **Run now** or the scan pivot MUST honor the existing prevention of duplicate concurrent runs of the same profile.
- **FR-020**: All pivot and launch actions MUST remain available to both Administrator and Operator roles (no new role restriction), while preserving existing role-gated boundaries elsewhere.

### Key Entities *(include if feature involves data)*

- **Host Selection**: The set of host addresses the operator has ticked on a run's results view. Transient, scoped to one results view; the input to both pivot actions. Not persisted as a durable record.
- **Run Launch Configuration**: The per-run settings shown in the Scan Configuration window — target scope, port specification, timing, extracted fields — originating from a profile but applied one-off to a single run without altering the profile.
- **Discovery Profile** *(existing)*: The saved scan definition selected for a run; its stored settings are the window's defaults and are never changed by a one-off launch.
- **Scan Run** *(existing)*: The discovery run created by **Start Scan**, carrying the one-off target and settings used.
- **Host Result** *(existing)*: A row in the results table (address, open ports, service/version, compliance findings) that can be selected and whose version-validity finding drives auto-select.
- **Credential Check** *(existing)*: The standalone credential-tool run initiated from the credential pivot, governed by the device-safety guardrails and the audit log.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From viewing a run's results, an operator can launch a follow-up scan on a chosen subset of hosts in 3 actions or fewer (select → choose profile → Start Scan) and under 30 seconds, without retyping any host address.
- **SC-002**: From viewing a run's results, an operator can start a credential check on a chosen subset of hosts without manually typing any host address.
- **SC-003**: The **Select invalid-version hosts** action selects 100% of the run's non-compliant-version hosts and 0% of its compliant or unknown-version hosts.
- **SC-004**: 100% of runs launched through the Scan Configuration window leave the originating profile's saved settings unchanged (verified before/after).
- **SC-005**: The legacy browser prompt for target entry appears in 0% of **Run now** launches after this feature ships.
- **SC-006**: 100% of credential checks started via the pivot are recorded in the audit log and demonstrably honor the ≥5-second cooldown and the attempt ceiling.
- **SC-007**: A target-less launch is blocked 100% of the time until a valid target is supplied (no run is ever created with an empty target).

## Assumptions

- **Pivot targets use displayed addresses**: Both pivots use the host addresses exactly as shown in the results table; per-host port/service details are not carried into the credential check automatically (the operator chooses them).
- **One-off semantics**: The Scan Configuration window is a launch step, not an edit step — changes never write back to the saved profile. Persisting profile changes remains the job of the profile editor.
- **"Invalid version" definition**: Auto-select keys on the version-validity compliance control; "invalid" means a non-compliant result, and both "unknown" (undetermined version) and "compliant" are excluded.
- **Window scope applies to every Run now**: Per the product decision, the Scan Configuration window opens on every Run now (targeted profiles are effectively one confirmation click; target-less profiles require a target before Start Scan), not only for target-less profiles.
- **Scan pivot confirmation**: Per the product decision, pivoting selected hosts into a scan routes through the Scan Configuration window (pre-filled with the selected hosts) rather than launching immediately, giving the operator a review/adjust step.
- **Field set reused**: The window reuses the profile editor's field controls, validation rules, and command-preview behavior for its four editable fields (target, ports, timing, extracted fields); the version-validity compliance toggle and NSE selection are inherited read-only from the saved profile, and no new scan parameters are introduced.
- **Pivot presentation**: Pivot actions navigate to the destination tool page (credential tool or Scan Configuration) with the target pre-filled, rather than opening an in-page overlay; the results view is left behind and browser Back returns to it. Host selection is therefore consumed by a single pivot action and is not required to survive the navigation.
- **Roles unchanged**: Both existing roles (Administrator, Operator) may perform all discovery actions, including these pivots and launches; no new role gate is added.
- **Reuses existing engines**: Scan launches reuse the existing run/launch path (including duplicate-run prevention and caching); credential checks reuse the existing standalone credential tool and its central guardrails and scheduler — no second mechanism is introduced.

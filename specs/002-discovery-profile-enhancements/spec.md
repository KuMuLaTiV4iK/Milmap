# Feature Specification: Milmap — Discovery Profile Enhancements, NSE Scripts, Configuration, Roles & Ukrainian SOC UI

**Feature Branch**: `002-discovery-profile-enhancements`

**Created**: 2026-10-21

**Status**: Draft

**Input**: User description (MVP feedback): "(1) default scan timing should be T3 with the operator free to change it; (2) add an Edit button for profiles; (3) make the default-vendor-credential check a separate tool (runnable on demand or on a schedule) rather than profile automation; (4) add a Configuration button where an operator can change their password and account/session security settings, set up user roles with an admin role that manages all users, and add NSE scripts to the allow-list; (5) give full control over nmap command building including NSE-script selection, and remove the host-management link from profiles/UI (it will become a separate standalone function later); (6) give the web UI a dark SOC design, in Ukrainian. Keep the air-gapped, defensive, internal-use posture."

## Context & Scope

This feature iterates on the existing **Asset Inventory & Compliance Management Dashboard** (feature `001-asset-compliance-dashboard`). As part of this iteration the application is renamed to **Milmap**. It does not change the product's purpose, deployment model, or security posture: an internal, **air-gapped**, defensive network-administration tool operated by the organization's own Network Systems Administrators against authorized internal infrastructure.

The scope covers four areas surfaced during MVP testing:

1. **Profile definition & execution** — profiles must be editable via a button, the operator must have full control over which vetted options compose the scan command (including choosing NSE scripts), new profiles must default to a standard `T3` timing template the operator can change, and the per-result host-management link is removed from profiles and the UI (to be reintroduced later as a separate standalone function).
2. **A standalone default-credential tool** — checking whether a device still accepts factory-default vendor credentials becomes a separate tool rather than an automated part of a discovery profile. The operator runs it on demand and may also configure it as a scheduled task (the same pattern applies to future standalone tools).
3. **A Configuration area** — a settings screen where operators change their own password, where administrators manage user accounts, roles and session security, and where the NSE-script allow-list is maintained.
4. **Presentation & localization** — the web UI adopts a dark, SOC-style visual theme, is presented in **Ukrainian**, and gives every configuration control a short inline help annotation (a `?` marker). Technical identifiers (script names, nmap timing templates, flags, port numbers) stay in their original English form.

All behavior remains offline: NSE scripts execute from the locally installed `nmap` only, with no script download or external lookup, and the default-credential catalog and reference datasets remain locally maintained.

## Clarifications

### Session 2026-10-21

- Q: Should the "extract open ports" and "extract service/firmware version" selections remain mandatory? → A: No. Both must be independently operator-controllable; a profile may select neither, either, or both. Service/firmware-version extraction implies service detection must be turned on; open-ports-only scans are permitted.
- Q: How fast must discovery be? → A: Not a requirement. New profiles simply default to the standard `T3` timing template and the operator may change it to any supported template (T0–T5). No performance targets are specified.
- Q: Should the default-vendor-credential check stay inside compliance-enabled profiles? → A: No. It becomes a **separate tool** the operator runs manually against a chosen target (and may also schedule); it no longer runs automatically as part of any discovery profile's run. It still honors the 3-attempt / 5-second-cooldown guard. (Offline version/firmware-validity compliance is unaffected and may remain a profile capability.)
- Q: What should the Configuration area let operators change, and who manages users? → A: Operators change their own password and account/session security settings; the system introduces user **roles** with an **Administrator** role that can manage all user accounts (create, edit, deactivate, assign roles, reset passwords). This supersedes feature 001's single-role assumption. The NSE-script allow-list is also maintained from the Configuration area.
- Q: Should the standalone default-credential tool be schedulable? → A: Yes. In addition to running on demand, the operator may configure it as a **scheduled task**. The same scheduling pattern applies to future standalone tools. The 3-attempt / 5-second-cooldown guard still applies to scheduled runs.
- Q: Language and app name? → A: The application is renamed **Milmap** and its UI is presented in **Ukrainian**; technical identifiers (NSE script names, nmap timing templates such as `T3`, flags, port numbers) remain in English. Every configuration control carries a short inline help annotation marked with a `?` (e.g., for `T3`: "Налаштування швидкості сканування").
- Q: What can a standard (non-Administrator) operator do? → A: Standard operators do all discovery work — create, edit, run, delete, and schedule profiles; run the standalone tools; and view history — but cannot manage users, account/session security settings, or the NSE allow-list, all of which are Administrator-only. Two roles only (Administrator, Operator); no read-only viewer role.
- Q: Should the standalone tool scheduler reuse the discovery-profile scheduling engine? → A: Yes — one shared scheduling engine. Tool tasks are another schedulable job type with the same next-run display, overlap prevention, missed-run catch-up, and audit behavior as discovery-profile schedules.
- Q: How are the default-credential tool's target(s) and service determined? → A: Each run/task stores an explicit target (hosts/CIDRs/ranges) plus the port/service to check; launching from a discovery result row prefills the host and its detected service. Catalog entries matching that service are tried. No linkage to a discovery profile's result set.
- Q: How does the first Administrator account come to exist on a fresh install? → A: The first account created on a fresh install is automatically an Administrator; accounts an Administrator creates afterward default to Operator (role changeable by an Administrator).
- Q: What happens to the host-management link in profiles? → A: It is removed entirely from discovery profiles and the web UI (superseding feature 001's host-link templates and per-result links), including all `{host}` placeholder handling. It will be delivered later as a separate standalone function and is out of scope for this feature.
- Q: Is the MikroTik RouterOS check a dedicated feature? → A: No — it was only an illustrative example of a useful NSE command. There is no MikroTik-specific user story or requirement; `mikrotik-routeros-version` may ship as one example entry in the default NSE allow-list, exercised through the general NSE capability.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Edit an existing profile via a button (Priority: P1)

An administrator opens a saved profile through an **Edit** button and changes it — name, target scope, ports, timing template, extracted fields, or NSE scripts — then saves. Today only Run now / Duplicate / Delete are offered, forcing the operator to recreate a profile to change anything.

**Why this priority**: Profiles are the central reusable object; iterating on them is a basic expectation and the absence of an Edit action blocks everyday tuning.

**Independent Test**: Open an existing profile via the Edit button, modify several fields, save, and confirm the changes persist and are used by the next run — with no new profile created.

**Acceptance Scenarios**:

1. **Given** an existing profile, **When** the operator clicks its **Edit** button, **Then** an editable form opens pre-populated with the profile's current values.
2. **Given** the edit form, **When** the operator changes fields and saves, **Then** the same profile is updated in place (no duplicate is created) and the new values are used by subsequent runs.
3. **Given** two operators editing the same profile, **When** one saves after the other changed it, **Then** the later save is prevented or flagged for reconciliation rather than silently overwriting (consistent with 001 FR-042).
4. **Given** the edit form, **When** the operator submits invalid values, **Then** the save is rejected with specific, field-level messages and the stored profile is unchanged.

---

### User Story 2 - Full operator control over the scan command (Priority: P1)

An administrator decides exactly which telemetry the scan extracts and which timing it uses. The "Extract open ports" and "Extract service/firmware version" options are genuinely selectable rather than forced/disabled; new profiles default to the `T3` timing template and the operator may change it to any supported template; and the operator can see the effective command the profile will run. Selecting service/firmware-version extraction turns on service detection; an open-ports-only scan is allowed. No free-form flag string is ever accepted — the command is composed only from the vetted options the operator selects (including any NSE scripts from User Story 4).

**Why this priority**: Operators need the orchestrated command to match their intent; forced options and a hidden command undermine trust and predictability.

**Independent Test**: Toggle each extraction option independently and change the timing template, confirm a profile can be saved with any combination (including open-ports-only), and confirm the effective-command preview reflects exactly the selected options.

**Acceptance Scenarios**:

1. **Given** the profile form, **When** the operator views the extraction options, **Then** "Extract open ports" and "Extract service/firmware version" are both interactive controls the operator can turn on or off independently (not disabled/forced).
2. **Given** a new profile, **When** the operator views the timing template, **Then** it defaults to `T3` and can be changed to any supported template (T0–T5).
3. **Given** service/firmware-version extraction is selected, **When** the profile is saved and run, **Then** service detection is applied so versions can be reported; **When** it is deselected, **Then** no service-detection probing occurs and results omit version data without error.
4. **Given** any valid combination of selected options, **When** the operator reviews the profile before running, **Then** the system shows the exact effective command (or complete flag set) that will be executed.
5. **Given** the command is composed, **When** any option is applied, **Then** it is drawn only from the vetted allow-list of options — no raw/free-form flag string is accepted — preserving the command-injection guard.

---

### User Story 3 - Configuration: account security, roles & user management (Priority: P1)

An operator opens a **Configuration** button/screen to change their own password and account/session security settings. The system now distinguishes user **roles**: an **Administrator** can manage all user accounts — create them, edit them, deactivate them, reset passwords, and assign roles — while a standard Operator manages only their own account. The same Configuration area is where the NSE-script allow-list is maintained (see User Story 4).

**Why this priority**: Introducing roles and letting an administrator manage users is foundational to safe multi-operator use, and the Configuration screen is the hub the operator explicitly asked for; it gates the allow-list management that NSE selection depends on.

**Independent Test**: As an administrator, open Configuration, create a second user and assign the Operator role; sign in as that user and confirm they can change their own password but cannot manage other users; confirm the admin can deactivate and reset that user.

**Acceptance Scenarios**:

1. **Given** any authenticated operator, **When** they open Configuration, **Then** they can change their own password (subject to the ≥ 20-character policy) and view the account/session security settings.
2. **Given** an administrator in Configuration, **When** they create, edit, deactivate, or assign a role to a user account, or reset a user's password, **Then** the change persists, takes effect on that user's next action/sign-in, and is recorded in the audit log.
3. **Given** a non-administrator operator, **When** they open Configuration, **Then** user-management, security-settings, and allow-list controls are not available to them and any attempt to use them is denied.
4. **Given** an administrator editing account/session security settings (e.g., password minimum length, lockout threshold/duration, session idle timeout), **When** they save, **Then** the new settings apply going forward, and the password minimum length cannot be set below the 20-character floor from feature 001.
5. **Given** a deactivated user, **When** they attempt to sign in, **Then** access is denied and the attempt is audit-logged.

---

### User Story 4 - Select NSE scripts; manage the allow-list in Configuration (Priority: P2)

An administrator enables one or more Nmap Scripting Engine (NSE) scripts on a profile by ticking them in a checklist. The checklist is populated from a curated allow-list of permitted scripts, which is maintained from the Configuration area — administrators add, update, or remove entries so new vetted scripts become available without redeploying. Allow-list changes are recorded in the audit log.

**Why this priority**: NSE scripts unlock targeted checks the operator needs, but they layer on top of the core command-control work and the Configuration area (both P1) that governs the allow-list guardrail.

**Independent Test**: In Configuration, add a script to the allow-list, confirm it appears in the profile checklist, select it on a profile, and confirm the run applies exactly the selected script(s); remove it from the allow-list and confirm it can no longer be selected.

**Acceptance Scenarios**:

1. **Given** a profile form, **When** the operator opens the NSE-script selector, **Then** a checklist of the currently allow-listed scripts is shown and any subset can be selected.
2. **Given** selected scripts, **When** the profile runs, **Then** exactly those scripts are applied to the scan and their output is captured in the results and persisted in history.
3. **Given** the allow-list editor in Configuration, **When** an administrator adds, edits, or removes a script entry and saves, **Then** the change persists, is reflected in every profile's checklist, and is recorded in the audit log with who changed it and when.
4. **Given** a profile referencing a script, **When** that script is later removed from the allow-list, **Then** the system prevents running the off-list script (the selection is disabled/flagged) rather than silently executing it.
5. **Given** the allow-list editor, **When** an administrator adds a script outside Nmap's vetted/"safe" categories, **Then** the system warns about the risk but still lets the administrator proceed.
6. **Given** a selected script that needs a port not present in the profile's port spec, **When** the operator saves/reviews the profile, **Then** the system warns the script may not run against any target.
7. **Given** the air-gapped environment, **When** a scripted scan runs, **Then** scripts execute only from the locally installed Nmap with no network/script download.

---

### User Story 5 - Standalone default-credential tool (on demand or scheduled) (Priority: P2)

An administrator runs the default-credential check as a **separate tool** against a chosen target (for example, selected from a discovery result row or entered directly) to see whether the device still accepts known factory-default vendor credentials. The tool is **not embedded in a discovery profile's run**; instead the operator runs it on demand or configures it as a **scheduled task**. The same standalone-tool pattern — on-demand plus its own schedule — applies to future tools. It remains strictly guarded whenever it runs: at most **3 attempts per target** with a **5-second cooldown** between attempts, using the locally maintained default-credential catalog, and it never persists the tried secrets in recoverable form.

**Why this priority**: Decoupling the check from discovery-profile automation while still allowing its own schedule is a deliberate safety/clarity change the operator requested; it is valuable but builds on discovery results already existing.

**Independent Test**: Launch the tool on demand against a host and confirm the 3-attempt / 5-second guard and audit logging; then configure it as a scheduled task, let it trigger, and confirm a scheduled run is produced and recorded exactly as the on-demand run — and that no discovery profile triggers the check as part of its own run.

**Acceptance Scenarios**:

1. **Given** a discovery result row or a manually specified target plus port/service, **When** the operator launches the default-credential tool, **Then** the check runs against that target only, trying the catalog entries matching the service.
2. **Given** the tool, **When** the operator configures it as a scheduled task with a target and recurrence, **Then** the task is saved, its next run time is shown, and at its scheduled time the check runs and is recorded in history/audit as an operator-equivalent run.
3. **Given** any run (on demand or scheduled), **When** it executes, **Then** it makes no more than 3 authentication attempts and waits at least 5 seconds between consecutive attempts.
4. **Given** a response body matching the expected success keywords/signatures for the vendor/service, **When** the check completes, **Then** the device is flagged non-compliant ("default credentials in use"); otherwise it is flagged compliant, and if the attempt limit is reached without a conclusive result it is flagged inconclusive.
5. **Given** any discovery profile's run, **When** it executes, **Then** it does not automatically perform the default-credential check (the check runs only when the operator initiates it or its own scheduled task triggers it).
6. **Given** a completed check, **When** results are recorded, **Then** the outcome is audit-logged and the specific credential secrets tried are not persisted in recoverable form.

---

### User Story 6 - Dark SOC interface in Ukrainian with inline help (Priority: P2)

Operators work in a dark, Security-Operations-Center-style interface, presented in **Ukrainian** and branded **Milmap**: a high-contrast dark palette suited to low-light monitoring, applied consistently across every screen (sign-in, profiles, results, history, configuration, and the default-credential tool). Every configuration control carries a short inline help annotation, marked with a `?`, that explains what it does (for example, the `T3` timing control shows "Налаштування швидкості сканування"). Technical identifiers — NSE script names, nmap timing templates, flags, and port numbers — remain in their original English form rather than being translated.

**Why this priority**: A consistent dark Ukrainian-language interface with inline help improves usability for the operators in a SOC setting and is an explicit request, but it is a presentation layer over the functional work.

**Independent Test**: Navigate every screen and confirm a consistent dark SOC theme with legible contrast, Ukrainian labels, the app branded Milmap, and a `?` help annotation on each configuration control — while technical identifiers stay in English.

**Acceptance Scenarios**:

1. **Given** any screen in the application, **When** it renders, **Then** it uses the dark SOC theme consistently (shared palette, typography, and component styling), presents its labels and messages in Ukrainian, and shows the product name as Milmap.
2. **Given** results and status indicators (e.g., running/failed, compliant/non-compliant), **When** they render on the dark theme, **Then** they remain clearly distinguishable with sufficient contrast.
3. **Given** any configuration control (e.g., timing template, extraction options, security settings, allow-list entry fields), **When** the operator views it, **Then** a `?` help annotation is available that shows a short Ukrainian explanation of the control.
4. **Given** a technical identifier such as `T3`, `-sV`, a port number, or an NSE script name, **When** it appears in the UI, **Then** it is shown in its original English form and not translated.

---

### Edge Cases

- **Legacy profiles saved with the old forced extraction fields**: continue to load and run; their extraction selections and timing template remain editable to any combination under the new rules.
- **Legacy profiles saved with a host-management link template**: load and run without error; the stored host-link value is ignored and no longer presented in the profile form or results (the capability is removed pending a future standalone function).
- **Profile with neither extraction option nor any NSE script selected**: still valid — it performs a basic port scan and reports responding hosts/open ports per its port spec without error.
- **NSE script removed from the allow-list while a scheduled profile still references it**: the scheduled run does not execute the off-list script; the condition is surfaced (e.g., the run is flagged) rather than silently dropping or silently running it.
- **Duplicate or malformed allow-list entry** (empty id, duplicate script id): rejected at save with a specific message.
- **A selected NSE script requires a port the profile does not scan**: the system warns the script may not run against any target.
- **Last administrator**: the system prevents deactivating or demoting the only remaining administrator so the deployment is never left with no one able to manage users.
- **Administrator resets a user's password / deactivates a user mid-session**: the affected user's existing session is invalidated at next action and re-authentication (or denial) follows.
- **Lowering the password minimum below 20**: rejected — the 20-character floor from feature 001 cannot be weakened via Configuration.
- **Default-credential tool reaching the attempt/cooldown limit**: stops immediately and reports "inconclusive"; never exceeds 3 attempts or shortens the 5-second cooldown.
- **Scheduled default-credential task overlapping a still-running check of the same target**: a conflicting concurrent run is prevented per the overlap policy (consistent with 001 scheduling behavior) rather than launching duplicates or exceeding the attempt guard.
- **Missing Ukrainian translation for a label**: the UI falls back to a readable value rather than showing a blank/broken label; technical identifiers are shown in English by design (not treated as missing translations).

## Requirements *(mandatory)*

### Functional Requirements

#### Timing Default

- **FR-001**: New profiles MUST default to the `T3` timing template, and the operator MUST be able to change the timing template to any supported value (T0–T5). No scan-performance target is imposed by this feature.

#### Profile Editing

- **FR-002**: The profile list/detail UI MUST expose an **Edit** button for every existing profile, alongside Run now / Duplicate / Delete.
- **FR-003**: Activating Edit MUST open an editable form pre-populated with the profile's current values; saving MUST update the same profile in place without creating a duplicate, applying the existing concurrency protection (no silent overwrite) and the same field-level validation as creation.

#### Host-Management Link Removal

- **FR-004**: The host-management link MUST be removed from discovery profiles and the web UI, superseding feature 001's host-management link templates (001 FR-013) and per-result host-link rendering (001 FR-019). The profile create/edit form MUST NOT present a host-link field, saving a profile MUST NOT perform any `{host}` placeholder validation, and result tables MUST NOT render a per-host management link. Any host-link value on a legacy profile MUST be ignored without error. (This capability is planned as a separate standalone function in a later iteration and is out of scope here.)

#### Full Operator Control of Telemetry Extraction

- **FR-005**: "Extract open ports" and "Extract service/firmware version" MUST be independently operator-controllable selections; neither may be forced/disabled, and the previous minimum-required-field constraint MUST be removed.
- **FR-006**: A profile MUST be valid with any combination of extraction selections, including open-ports-only and none selected.
- **FR-007**: When service/firmware-version extraction is selected, the system MUST enable service detection so versions can be reported; when deselected, the system MUST NOT perform service-detection probing and MUST report results without version data and without error.
- **FR-008**: Before running, the system MUST let the operator view the exact effective command (or the complete ordered flag set) a profile will execute.
- **FR-009**: The orchestrated scan command MUST be composed solely from vetted, allow-listed options reflecting the operator's selections; the system MUST NOT accept or forward any raw/free-form flag string (preserving the command-injection guard).

#### NSE Script Support

- **FR-010**: A profile MUST allow selection of zero or more NSE scripts from a checklist populated by the current allow-list, and MUST apply exactly the selected scripts to the scan.
- **FR-011**: The system MUST capture and display each selected script's output per host in the results and persist it in history alongside other telemetry.
- **FR-012**: The NSE-script allow-list MUST be maintainable from the Configuration area by Administrators — adding, updating, and removing entries — with changes persisted and reflected in all profiles' checklists.
- **FR-013**: A profile MUST NOT be able to run a script that is not currently on the allow-list; selections referencing a removed script MUST be prevented/flagged rather than silently executed.
- **FR-014**: The system MUST record allow-list changes (add/update/remove) in the audit log, including the acting administrator and timestamp.
- **FR-015**: The default allow-list MUST ship with a curated set of vetted/"safe" scripts (for example, `mikrotik-routeros-version` as one such entry).
- **FR-016**: When an administrator adds a script outside Nmap's vetted/"safe" categories, the system MUST surface a warning while still allowing the administrator to proceed.
- **FR-017**: NSE scripts MUST execute only from the locally installed Nmap with no network or script download.
- **FR-018**: Allow-list entries MUST be validated at save (non-empty script identifier, no duplicates), rejecting malformed entries with a specific message.
- **FR-019**: When a selected script needs a port not present in the profile's port spec, the system SHOULD warn that the script may not run against any target.

#### Standalone Default-Credential Tool (on demand or scheduled)

- **FR-020**: The default-credential check MUST be a separate tool that runs against an explicit target (hosts/CIDRs/ranges) plus a chosen port/service, and MUST NOT run as part of any discovery profile's run. Launching the tool from a discovery result row MUST prefill the host and its detected service; the catalog entries matching that service are the ones tried. A run/task is self-contained and is NOT linked to a discovery profile's result set.
- **FR-021**: The operator MUST be able to run the tool on demand AND to configure it as a scheduled task, with the next run time displayed; a scheduled run MUST produce and record a result equivalent to an on-demand run. Tool scheduling MUST use the same scheduling engine as discovery-profile schedules — inheriting its next-run display, overlap prevention, missed-run catch-up, and audit behavior — with tool tasks represented as a distinct job type (not attached to a discovery profile). The system SHOULD support this standalone on-demand-plus-schedule pattern for future tools, not only the default-credential tool.
- **FR-022**: Every run of the tool (on demand or scheduled) MUST make no more than 3 authentication attempts per target and MUST enforce a cooldown of at least 5 seconds between consecutive attempts.
- **FR-023**: The check MUST determine success by matching the device's response body against the expected success keywords/signatures for the vendor/service from the local default-credential catalog, flagging the asset non-compliant ("default credentials in use"), compliant, or inconclusive when the attempt limit is reached without a conclusive result.
- **FR-024**: The tool MUST record its outcome in the audit log and MUST NOT persist the specific credential secrets tried in recoverable form.
- **FR-025**: The offline version/firmware-validity compliance capability from feature 001 is unaffected by this change and MAY remain a profile capability; only the default-credential check is decoupled into the standalone tool.

#### Configuration, Accounts & Roles

- **FR-026**: The application MUST provide a **Configuration** area, reachable via a button, where an authenticated operator can change their own password (subject to the ≥ 20-character policy) and view account/session security settings.
- **FR-027**: The system MUST support exactly two user **roles** — **Administrator** and **Operator** (no read-only viewer role) — and MUST govern access to Administrator-only functions by role.
- **FR-028**: Operators MUST be able to perform all discovery work — create, edit, run, delete, and schedule discovery profiles; run the standalone tools; and view results/history — while user management, account/session security settings, and NSE allow-list management are **Administrator-only**.
- **FR-029**: An Administrator MUST be able to manage all user accounts — create, edit, deactivate, assign/change roles, and reset passwords — with each action persisted and audit-logged.
- **FR-030**: On a fresh install the first account created MUST be assigned the Administrator role; accounts created afterward by an Administrator MUST default to the Operator role (changeable by an Administrator).
- **FR-031**: Operators MUST NOT be able to manage users, change account/session security settings, or edit the NSE allow-list; attempts to do so MUST be denied.
- **FR-032**: Administrators MUST be able to adjust account/session security settings (e.g., password minimum length, lockout threshold/duration, session idle timeout), and the system MUST reject any password minimum length below the 20-character floor established in feature 001.
- **FR-033**: The system MUST prevent an action that would leave the deployment with no active Administrator (e.g., deactivating or demoting the last administrator).
- **FR-034**: Deactivated users MUST be denied sign-in, and administrator-initiated deactivation or password reset MUST invalidate the affected user's active session at next action, with the event audit-logged.

#### Presentation & Localization

- **FR-035**: The web UI MUST use a dark, SOC-style visual theme applied consistently across all screens, with status and result indicators rendered at sufficient contrast to remain clearly distinguishable.
- **FR-036**: The application MUST be branded **Milmap**, with the name reflected in the UI (e.g., title/header) in place of the former dashboard name.
- **FR-037**: The UI MUST present its labels, messages, and help text in **Ukrainian**, while keeping technical identifiers (NSE script names, nmap timing templates such as `T3`, flags, and port numbers) in their original English form.
- **FR-038**: Every configuration control MUST provide a short inline help annotation, marked with a `?`, giving a concise Ukrainian explanation of what the control does (e.g., for the `T3` timing control: "Налаштування швидкості сканування").

### Key Entities *(include if feature involves data)*

- **Asset Discovery Profile** (extended): timing template defaults to `T3` and is operator-changeable; extraction selections (open ports, service/firmware version) are independent and non-mandatory; the profile carries a set of selected NSE scripts referencing allow-list entries. The host-management link is removed from the profile, and the profile no longer triggers the default-credential check.
- **User Account & Role** (extended): each account has one of two roles — Administrator or Operator. Administrators manage all accounts; the role determines access to user management, security settings, and allow-list management. Attributes: username, protected password material, role, active/deactivated state, lockout/throttle state, audit trail.
- **Configuration / Security Settings** (new): locally maintained settings for account/session security — password minimum length (≥ 20 floor), lockout threshold/duration, session idle timeout — plus the entry point to user management and allow-list management.
- **NSE Script Allow-List Entry** (new): a vetted script selectable on profiles. Attributes: script identifier/name, description, optional category/safety classification, optional associated/expected ports, enabled state, and provenance (who added/changed it and when). Maintained from Configuration.
- **Default-Credential Check (standalone tool)** (reframed): a check against an explicit target + port/service, bounded to 3 attempts / 5-second cooldown, producing a compliance outcome recorded in the audit log; not part of a discovery profile's run. Runs on demand or via its own scheduled task.
- **Scheduled Tool Task** (new): a schedulable job (job type distinct from a discovery-profile schedule) that runs a standalone tool (initially the default-credential tool) on the shared scheduling engine. Attributes: tool reference, explicit target (hosts/CIDRs/ranges), port/service to check, recurrence definition, enabled state, next-run time, overlap/catch-up behavior inherited from the shared engine.
- **UI Localization & Help Text** (new, reference): Ukrainian labels/messages plus a short help annotation per configuration control; technical identifiers remain English. Maintained as application-provided content.
- **Discovery Run / Host Result** (extended): host results additionally carry per-host NSE script output, persisted in history; the per-result host-management link is removed.
- **Audit Log Entry** (reused): additionally records allow-list changes, user-management actions, configuration changes, and default-credential checks.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: New profiles default to the `T3` timing template, and an operator can change the timing template to any of T0–T5 and have it applied to the run.
- **SC-002**: 100% of existing profiles can be opened via the Edit button, modified, and saved in place with changes persisted and no duplicate created.
- **SC-003**: An operator can save and run a profile with any combination of extraction selections — including open-ports-only and none — in 100% of cases, and the effective-command preview matches the selections exactly.
- **SC-004**: The profile create/edit form presents no host-management link field, saving performs no `{host}` validation, and result tables render no per-host management link.
- **SC-005**: An administrator can add a vetted script to the allow-list from Configuration and have it appear in the profile checklist, then run a profile applying exactly the selected scripts, without any application redeploy.
- **SC-006**: The default-credential check never runs as part of a discovery profile's run; it runs only when an operator initiates it or its own scheduled task triggers it, and across 100% of runs makes at most 3 attempts with ≥ 5 seconds between them — verifiable from the audit log.
- **SC-007**: The operator can configure the default-credential tool as a scheduled task, see its next run time, and have a scheduled run produce a recorded result equivalent to an on-demand run.
- **SC-008**: An administrator can create a user, assign the Operator role, and that user can change their own password but cannot manage other users, security settings, or the allow-list; the administrator can deactivate and reset that user — all actions appearing in the audit log.
- **SC-009**: The system never allows the password minimum length to be set below 20 and never allows the last administrator to be removed/demoted.
- **SC-010**: Every screen renders in the dark SOC theme (branded Milmap) with no light/unstyled screens, status/result indicators remain legible, UI text is in Ukrainian while technical identifiers stay English, and every configuration control exposes a `?` help annotation.

## Assumptions

- **Builds on feature 001**: This iteration reuses the authentication, persistence, history, caching, scheduling, offline version-validity compliance, concurrency, and audit-log capabilities from `001-asset-compliance-dashboard`; only the areas described here change.
- **Role model supersedes 001's single-role assumption**: Feature 001 assumed every operator is an administrator. This feature introduces exactly two roles — Administrator and Operator. Permission split (confirmed): both roles create/edit/run/delete/schedule profiles, review results/history, and use the standalone tools; only Administrators manage users, roles, account/session security settings, and the NSE allow-list. No read-only viewer role.
- **Host-management link removed**: The per-result host-management link and its profile template (feature 001 FR-013/FR-019) are removed from profiles and the UI in this iteration. The capability is planned as a separate standalone function in a later feature; migrating or reusing any stored legacy host-link values is out of scope here.
- **Timing only**: "Default T3, changeable" replaces any scan-speed/performance requirement; no wall-clock target is specified or tested by this feature.
- **Domain tool naming**: `nmap` and NSE script identifiers (e.g., `mikrotik-routeros-version`) appear by name because they are operator-designated domain dependencies (as in feature 001), not dashboard implementation choices; MikroTik is used only as an example entry in the default allow-list, not a dedicated feature.
- **Safety classification source**: "Vetted/safe" refers to Nmap's own script categories as the reference for the FR-016 warning; the allow-list remains the authoritative guardrail.
- **Air-gapped**: NSE scripts run only from the local Nmap install; the default-credential catalog and reference datasets remain locally maintained with no external lookups.
- **Dark SOC theme**: a single dark, high-contrast theme is in scope; a user-selectable light/dark toggle is not required for this iteration.
- **Localization**: the UI ships in a single language, Ukrainian; a runtime language switcher/multi-locale support is out of scope. Technical identifiers (script names, nmap timing templates/flags, ports) are intentionally kept in English.
- **App rename**: "Milmap" replaces the former product name in the UI; underlying data from feature 001 is retained (this is a rename, not a data migration).
- **Scheduled standalone tools**: the default-credential tool is the first standalone tool to support its own schedule; the "on demand plus independent schedule" pattern is intended to extend to future tools but no additional tool is defined in this iteration.
- **Out of scope**: the host-management link capability (deferred to a later standalone function); raw/free-form nmap flag entry; fetching new NSE scripts from outside the local Nmap install; changing the 3-attempt / 5-second-cooldown limits; multi-language/locale switching; and granular per-permission RBAC beyond the Administrator vs Operator split described above.

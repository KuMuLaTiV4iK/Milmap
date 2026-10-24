# Feature Specification: UI Layout Refinements

**Feature Branch**: `006-ui-layout-refinements`

**Created**: 2026-10-22

**Status**: Draft

**Input**: User description: "UI redesign for the dashboard — remove redundant headings and columns, reorganize the Home page into a two-column layout with a scheduled-tasks list, keep the nmap command preview visible without a target, make the ports field show its full contents, and split the Configuration page into role-aware subtabs that fold the version dictionary in."

## Clarifications

### Session 2026-10-22

- Q: When the version dictionary moves into Configuration Subtab 2, what happens to its current standalone top-nav link? → A: Remove the standalone link — the version dictionary is reachable only inside Configuration.
- Q: In the Home recent-scans list, should the "Не відповідає" (non-compliant) column stay after removing "Відповідає", "Невідомо", and "Непереконливо"? → A: Keep "Не відповідає" as the single at-a-glance compliance signal.
- Q: How should the "last 5" scheduled tasks on the Home page be ordered? → A: By next scheduled run, soonest first.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Faster Home-page overview (Priority: P1)

As a Network Systems Administrator, when I open the Home page I want the most useful information laid out side-by-side — my discovery profiles on the left and recent scan activity on the right — without filler headings, so I can take action (run a profile, open a scan) in fewer eye movements.

**Why this priority**: The Home page is the first screen every session; a clearer, denser layout improves every subsequent task and is independently valuable even if nothing else changes.

**Independent Test**: Load the Home page as an authenticated user with at least one profile and several recent scans; confirm the two-column layout renders, the removed heading/subtitle are gone, and the recent-scans list shows only the retained columns.

**Acceptance Scenarios**:

1. **Given** an authenticated user on the Home page, **When** the page loads, **Then** the "Головна" heading and the "Останні профілі виявлення та останні запуски сканування." subtitle are not displayed.
2. **Given** the Home page has rendered, **When** the user views the layout on a standard desktop width, **Then** the recent-profiles list appears in a left column and the recent-scans list appears in a right column.
3. **Given** recent scans exist, **When** the recent-scans list renders, **Then** it does not display the "Відповідає", "Невідомо", or "Непереконливо" columns, while the remaining columns (profile, last run, non-compliant count, and the per-row actions) are still shown.
4. **Given** the user is on a narrow/mobile-width viewport, **When** the Home page renders, **Then** the two columns stack vertically without horizontal scrolling and all content remains reachable.

---

### User Story 2 - Reach scheduled tasks from Home (Priority: P2)

As an administrator planning recurring work, I want to see my latest scheduled tasks right under the profiles list on the Home page and jump straight to the Schedules page by clicking one, so I can review and adjust automation without hunting through the nav.

**Why this priority**: Convenience that builds on the new Home layout (US1); valuable but not required for the layout itself to ship.

**Independent Test**: With at least one schedule configured, load the Home page and confirm up to five most-recent scheduled tasks appear beneath the profiles list and that clicking one navigates to the Schedules page.

**Acceptance Scenarios**:

1. **Given** scheduled tasks exist, **When** the Home page loads, **Then** the five most-recent scheduled tasks are listed under the profiles list in the left column.
2. **Given** more than five scheduled tasks exist, **When** the list renders, **Then** at most five are shown.
3. **Given** the scheduled-tasks list is shown, **When** the user clicks a scheduled task entry, **Then** they are taken to the Schedules page.
4. **Given** no scheduled tasks exist, **When** the Home page loads, **Then** the section renders an empty/placeholder state without error.

---

### User Story 3 - Clearer profile editing (Priority: P2)

As an administrator building a discovery profile, I want to preview the nmap command even before I enter a target, and I want the ports field to show everything I typed, so I can verify my configuration without guesswork or clipped text.

**Why this priority**: Directly reduces configuration errors on a core workflow; independent of the Home-page work.

**Independent Test**: Open the profile editor with no target set and confirm a command preview is shown; type a long comma-separated port list and confirm the full list stays visible.

**Acceptance Scenarios**:

1. **Given** the profile create/edit form with the target field empty, **When** the form renders, **Then** the nmap command preview is displayed (using a clearly-marked placeholder in place of the missing target) rather than being blank or hidden.
2. **Given** the user later enters a target, **When** the target value changes, **Then** the command preview updates to reflect it.
3. **Given** the ports field contains a long comma-separated list that exceeds one line, **When** the user views the field, **Then** the full list is visible — the field expands or is resizable to use the available space rather than clipping the text.

---

### User Story 4 - Simpler Profiles and History tables (Priority: P3)

As a user scanning tables of profiles and history, I want columns that add no value removed, so the tables are easier to read.

**Why this priority**: Low-risk readability cleanup; independent of all other stories.

**Independent Test**: Open the Profiles page and confirm the "Розклад" column is gone; open the History page and confirm the "З кешу?" column is gone.

**Acceptance Scenarios**:

1. **Given** the Profiles page, **When** the profiles table renders, **Then** the "Розклад" column (header and all cells) is not present and the remaining columns are unaffected.
2. **Given** the History page, **When** the history table renders, **Then** the "З кешу?" column (header and all cells) is not present and the remaining columns are unaffected.

---

### User Story 5 - Role-aware Configuration subtabs (Priority: P2)

As an administrator, I want the Configuration page organized into two subtabs — one for user management and session/security settings, another for NSE scripts and the version dictionary — so related controls are grouped. As an operator, I want the Configuration page to show only the controls I'm allowed to use (my own credentials and the version dictionary), so I'm not shown administrative controls I cannot use.

**Why this priority**: Improves organization and reinforces least-privilege presentation; builds on existing role separation.

**Independent Test**: Sign in as an administrator and confirm both subtabs with the specified grouping; sign in as an operator and confirm only own-credentials management and version-dictionary management are shown.

**Acceptance Scenarios**:

1. **Given** an administrator on the Configuration page, **When** it loads, **Then** two subtabs are presented: Subtab 1 contains user management and session/security settings; Subtab 2 contains NSE-script allow-list management and the version dictionary.
2. **Given** an administrator, **When** they switch between subtabs, **Then** the corresponding grouping is shown without a full page reload interrupting their work.
3. **Given** the version dictionary previously reached from its own navigation entry, **When** this change is in effect, **Then** version-dictionary management is available within Configuration Subtab 2.
4. **Given** an operator on the Configuration page, **When** it loads, **Then** only own-credentials (password change) management and version-dictionary management are visible; user management, session/security settings, and NSE allow-list controls are not shown.
5. **Given** an operator, **When** they attempt to reach an administrator-only configuration action by any means, **Then** the action is denied by the server (not merely hidden), consistent with existing role enforcement.

---

### Edge Cases

- **Empty states**: Home page with no profiles, no scans, and/or no schedules must render each section's empty state without error.
- **Narrow viewport**: The two-column Home layout and the resizable ports field must remain usable on small screens with no horizontal page scroll.
- **Command preview without extracted fields**: Preview must render sensibly when the target is empty AND optional toggles (ports, version detection, NSE scripts) are in any combination.
- **Operator navigating directly to a removed/standalone version-dictionary URL**: If the standalone version-dictionary navigation entry is removed, operators must still be able to manage the version dictionary via Configuration; any legacy direct link must not strand the user.
- **Scheduled-task click target**: Clicking anywhere on a scheduled-task row should route to Schedules consistently; keyboard activation should work too.

## Requirements *(mandatory)*

### Functional Requirements

#### Home page

- **FR-001**: The Home page MUST NOT display the "Головна" heading or the "Останні профілі виявлення та останні запуски сканування." subtitle.
- **FR-002**: The Home page MUST present the recent-profiles list in a left column and the recent-scans list in a right column on standard desktop widths, collapsing to a stacked layout on narrow widths without horizontal page scroll.
- **FR-003**: The Home page MUST display, beneath the profiles list in the left column, the five scheduled tasks whose next scheduled run is soonest (ordered soonest-first).
- **FR-004**: Each scheduled-task entry on the Home page MUST navigate the user to the Schedules page when activated (click or keyboard).
- **FR-005**: The recent-scans list on the Home page MUST NOT include the "Відповідає", "Невідомо", or "Непереконливо" columns; it MUST retain the profile, last-run timestamp, non-compliant ("Не відповідає") indicator, and per-row actions.
- **FR-006**: Each Home-page section (profiles, scans, scheduled tasks) MUST render a non-error empty state when it has no items.

#### Profiles page & profile editor

- **FR-007**: The Profiles table MUST NOT include the "Розклад" column (header or cells).
- **FR-008**: The profile create/edit form MUST display the nmap command preview even when no target is set, substituting a clearly-marked placeholder for the absent target.
- **FR-009**: The command preview MUST update to reflect the target once a target value is entered.
- **FR-010**: The ports input field MUST allow its full entered contents to be viewed — by expanding or being user-resizable — so a long comma-separated port list is not clipped within the available space.

#### History page

- **FR-011**: The History table MUST NOT include the "З кешу?" column (header or cells); the remaining columns MUST be unaffected.

#### Configuration page

- **FR-012**: For Administrators, the Configuration page MUST organize its controls into two subtabs: Subtab 1 = user management and session/security settings; Subtab 2 = NSE-script allow-list management and the version dictionary.
- **FR-013**: Version-dictionary management MUST be reachable within Configuration Subtab 2 (moved from its standalone location).
- **FR-013a**: The standalone version-dictionary ("Довідник версій") top-navigation entry MUST be removed; the version dictionary MUST be reachable only through the Configuration page (Subtab 2 for Administrators; the reduced Configuration view for Operators).
- **FR-014**: For Operators, the Configuration page MUST show only own-credentials (password change) management and version-dictionary management; user management, session/security settings, and NSE allow-list controls MUST NOT be shown.
- **FR-015**: Role-based restriction of administrator-only configuration actions MUST continue to be enforced server-side, not solely by hiding controls in the UI (consistent with existing behavior).
- **FR-016**: Switching between the Administrator Configuration subtabs MUST NOT lose unsaved context in the other subtab's forms due to a full page reload triggered by the switch itself. *(Soft requirement; see Assumptions.)*

#### Cross-cutting

- **FR-017**: All retained and new UI text MUST use the existing single-locale (Ukrainian) catalog; no new free-form hard-coded user-facing strings that bypass the catalog.
- **FR-018**: No change in this feature may expand what an Operator can do beyond discovery work plus own-credentials and version-dictionary management, nor relax any device-safety, credential-handling, or audit behavior.

### Key Entities *(include if feature involves data)*

- **Discovery Profile**: Existing entity; its list appears on Home (left column) and in the Profiles table (minus the schedule column). No schema change required by this feature.
- **Scan Run**: Existing entity; summarized in the Home recent-scans list (reduced columns) and the History table (minus the cache-origin column).
- **Scheduled Task**: Existing entity; its five most-recent instances are surfaced on Home and link to the Schedules page.
- **NSE Script Allow-list Entry**: Existing entity; relocated to Configuration Subtab 2 (administrator-only).
- **Version Dictionary (Reference Versions)**: Existing reference dataset; management relocated into Configuration Subtab 2 and made available to Operators.
- **User / Role**: Existing entities; drive which Configuration controls are visible and permitted.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the Home page, 100% of the specified removed elements (the heading, the subtitle, and the three scan columns) are absent, and the profiles/scans two-column split plus the scheduled-tasks list are present, verified by inspection on a standard desktop width.
- **SC-002**: From the Home page, a user can reach the Schedules page by activating a scheduled-task entry in a single action.
- **SC-003**: In the profile editor, the nmap command preview is visible before any target is entered in 100% of loads, and updates after a target is entered.
- **SC-004**: A port list of at least 20 comma-separated entries is fully readable in the ports field without the user needing to scroll inside a clipped single-line control.
- **SC-005**: The "Розклад" column is absent from the Profiles table and the "З кешу?" column is absent from the History table in 100% of loads.
- **SC-006**: An Administrator sees exactly the two specified Configuration subtabs with the specified grouping; an Operator sees only own-credentials and version-dictionary management — verified for both roles.
- **SC-007**: No regression in role enforcement: every administrator-only configuration action remains denied for Operators at the server, verified by the existing role-based access-control checks.
- **SC-008**: All Home, Profiles, History, and Configuration views render without horizontal page scroll at a narrow (mobile) width.

## Assumptions

- **A-001**: "Version dictionary" refers to the existing Reference Versions management (the "Довідник версій" area). Per clarification, its standalone navigation entry is removed; it is reachable only through the Configuration page (see FR-013a).
- **A-002**: Per clarification, the recent-scans list keeps the non-compliant ("Не відповідає") column as the single at-a-glance compliance signal; "Відповідає", "Невідомо", and "Непереконливо" are removed.
- **A-003**: "Own credentials" for Operators means the existing self-service password change already present on the Configuration page, not management of other users.
- **A-004**: Operators may manage the version dictionary (reference versions), consistent with their discovery/compliance duties; this does not grant any administrator-only capability and does not conflict with the constitution's least-privilege role model (NSE allow-list, user management, and security settings remain administrator-only).
- **A-005**: Subtabs are an in-page view toggle on the single Configuration page, not separate browser routes; FR-016 is best-effort and may be simplified at plan time if it conflicts with the existing per-card load pattern.
- **A-006**: Per clarification, the "last five" scheduled tasks are ordered by next scheduled run, soonest first (see FR-003).
- **A-007**: This is a presentation/layout feature; it introduces no new persisted data and no new backend endpoints beyond what already serves profiles, scans, schedules, reference versions, and configuration.

# Feature Specification: One-Time & Unit-Based Interval Schedules

**Feature Branch**: `005-schedule-recurrence-types`

**Created**: 2026-10-22

**Status**: Draft

**Input**: User description: "I can only set an interval schedule task; add a one-time (once) schedule task too. Fix the time/date setting approach: (1) list 'once' above 'interval'; (2) for 'once' add a calendar to set day, hours in 24h format, then minutes, in that order; (3) for 'interval' do not set an absolute time — instead choose the interval unit from a drop-down: minute, hour, day, week, month (UI in Ukrainian). First make the spec."

## Context & Problem

The discovery-schedule creation form on the `/schedules` page currently offers two recurrence
choices — "interval (seconds)" and "daily (hour:minute)". Two problems:

- There is **no way to schedule a scan to run just once** at a chosen future date and time. Every
  schedule is recurring.
- The **interval** option is entered as a raw number of seconds, which is awkward and error-prone
  (e.g., "every 2 weeks" means typing 1209600), and the "daily" option mixes an absolute clock time
  into what should be a simple cadence choice.

Operators think in terms of "run this once, next Tuesday at 14:30" or "run this every 2 hours" —
not seconds. This feature replaces the current recurrence choices for discovery schedules with two
clear kinds — **одноразово (once)** and **періодично/інтервал (interval)** — a one-time run picked
on a calendar at a 24-hour time, and a recurring run expressed as "every N <unit>" with the unit
chosen from a Ukrainian drop-down (minute, hour, day, week, month).

The recurring-schedule engine is **shared** with the standalone credential-tool tasks, so this
change must extend the recurrence model without breaking those existing tasks.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Schedule a scan to run once at a chosen date and time (Priority: P1)

An operator creating a schedule chooses "одноразово" (once) — the first option in the list — picks a
calendar day, then an hour in 24-hour format, then a minute, and saves. The scan runs exactly once at
that date and time and then does not run again; the schedule remains visible showing that it has
completed.

**Why this priority**: This is the new capability the operator explicitly asked for and the headline
of the feature. A one-time scheduled scan (e.g., "run this profile tonight at 23:00") is not possible
today at all.

**Independent Test**: Create a "once" schedule for a near-future date/time, confirm it is saved and
listed; let the heartbeat reach that time; confirm the scan runs exactly once and the schedule is
then shown as completed and does not fire again.

**Acceptance Scenarios**:

1. **Given** the create-schedule form, **When** the operator selects "once", **Then** the form shows
   a calendar day picker, an hour field (0–23), and a minute field (0–59), in that order, and no
   interval/unit fields.
2. **Given** a "once" selection with a future day/hour/minute, **When** the operator saves, **Then**
   the schedule is created with that exact run time and appears in the list.
3. **Given** a saved "once" schedule whose time has arrived, **When** the heartbeat runs, **Then** the
   scan is triggered exactly once.
4. **Given** a "once" schedule that has already fired, **When** the heartbeat runs again, **Then** the
   scan is **not** triggered again, and the schedule is shown as completed.
5. **Given** a "once" selection with a day/time in the past, **When** the operator saves, **Then** the
   save is rejected with a clear inline message and no schedule is created.

---

### User Story 2 - Schedule a recurring scan by interval unit (Priority: P2)

An operator who wants a recurring scan chooses "інтервал" (interval), enters a whole number, and
chooses a unit from a drop-down — хвилина (minute), година (hour), день (day), тиждень (week), or
місяць (month). The scan then runs every N of that unit. The operator does not enter any absolute
clock time for an interval schedule.

**Why this priority**: This replaces the current raw-seconds interval entry with something operators
can actually reason about, and it covers the recurring use cases. It builds on the same form as User
Story 1 but is independently valuable and testable.

**Independent Test**: Create an interval schedule of "every 2 hours", confirm it is saved; advance the
clock/heartbeat and confirm it fires on that cadence and reschedules itself for the next interval.

**Acceptance Scenarios**:

1. **Given** the create-schedule form, **When** the operator selects "interval", **Then** the form
   shows a whole-number field and a unit drop-down offering exactly: minute, hour, day, week, month —
   and no absolute time fields.
2. **Given** an interval of "every 2 hours", **When** the operator saves, **Then** the schedule is
   created and its next run is two hours after creation.
3. **Given** an interval schedule that just fired, **When** the heartbeat processes it, **Then** its
   next run is scheduled one further interval ahead (it keeps recurring).
4. **Given** an interval of "every 1 month", **When** the next run is computed, **Then** it is the
   same day-of-month and time one calendar month later, handling months where that day does not exist
   gracefully (no crash, no skipped-forever schedule).
5. **Given** an interval with a zero, negative, empty, or non-whole number, **When** the operator
   saves, **Then** the save is rejected with a clear inline message.

---

### User Story 3 - A clear, correctly ordered, Ukrainian scheduling form (Priority: P3)

The scheduling form reads naturally for a Ukrainian-speaking operator: the recurrence-kind selector
lists "одноразово" above "інтервал"; the one-time inputs are ordered day → hour (24h) → minute; the
interval unit drop-down is fully in Ukrainian; and validation problems appear inline on the form
rather than as a browser error dialog or a server error page.

**Why this priority**: The underlying capability (US1, US2) is what matters; this story is the
presentation and localization polish that makes it usable and consistent with the rest of the
Ukrainian UI. It is the lowest priority because the schedules still function without it.

**Independent Test**: Open the create-schedule form and confirm the ordering, the Ukrainian labels for
both kinds and all five interval units, 24-hour time entry, and that an invalid entry surfaces inline.

**Acceptance Scenarios**:

1. **Given** the recurrence-kind selector, **When** it is opened, **Then** "once" appears above
   "interval", both labeled in Ukrainian.
2. **Given** the "once" inputs, **When** displayed, **Then** the hour accepts 0–23 (24-hour format)
   and the fields are ordered day, then hour, then minute.
3. **Given** the interval unit drop-down, **When** opened, **Then** all five units are shown in
   Ukrainian.
4. **Given** an invalid submission, **When** the operator saves, **Then** the error is shown inline on
   the form and the rest of the page is unaffected.

---

### User Story 4 - Edit an existing schedule (Priority: P3)

An operator can edit a schedule already in the list — changing its recurrence (switching between once
and interval, or adjusting the time/cadence), its target, its label, and whether it is enabled —
without having to delete it and create a new one. Editing uses the same controls as creation and is
validated and audited the same way.

**Why this priority**: Operators routinely need to adjust a schedule (fix a wrong time, change the
cadence, pause it). Today the list offers only delete, forcing a delete-and-recreate. It is P3 because
it reuses the create form and the already-existing update capability, and the schedules are usable
without it.

**Independent Test**: With a saved schedule, open its edit affordance, change its recurrence (e.g.
from "every 2 hours" to a one-time run, or change the target/label/enabled), save, and confirm the
schedule row reflects the change and its next run is recomputed; invalid edits are rejected inline.

**Acceptance Scenarios**:

1. **Given** a schedule in the list, **When** the operator chooses to edit it, **Then** the form is
   populated with that schedule's current recurrence kind and values, target, label, and enabled
   state.
2. **Given** an edit that changes the recurrence or cadence, **When** the operator saves, **Then** the
   schedule is updated in place, its next run is recomputed, and the change is recorded in the audit
   log — without creating a second schedule.
3. **Given** an edit with an invalid recurrence (e.g. a past one-time time or a non-positive
   interval), **When** the operator saves, **Then** it is rejected with a clear inline message and the
   schedule is left unchanged.
4. **Given** a completed one-time schedule, **When** the operator edits it to a new future time and
   enables it, **Then** it becomes active again and will fire at the new time.

---

### Edge Cases

- **Once time in the past** (including a time that passes between opening the form and saving):
  rejected with a clear message (US1 scenario 5).
- **Once completion**: after it fires, the schedule must not run again and must be clearly marked as
  completed; disabling/enabling or deleting it still behaves sensibly.
- **Interval month roll-over**: "every 1 month" starting on the 31st lands on a valid day in months
  with fewer days, without crashing or stalling (US2 scenario 4).
- **Interval non-positive / non-integer count**: rejected (US2 scenario 5).
- **Heartbeat granularity**: a scan fires within one heartbeat cycle of its scheduled time, not to the
  exact second — acceptable and expected.
- **Shared engine / credential-tool tasks**: existing standalone credential-tool scheduled tasks must
  keep running; changing the recurrence model must not break any recurrence they already use.
- **Target still required**: a schedule still needs a target (its own or inherited from the profile);
  the recurrence change does not alter the target rules.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The discovery-schedule create/edit form MUST offer exactly two recurrence kinds — once
  and interval — with **once listed above interval**, both labeled in Ukrainian.
- **FR-002**: For a **once** schedule, the operator MUST set a calendar day, an hour in 24-hour format
  (0–23), and a minute (0–59), presented in that order; a once schedule MUST NOT ask for any interval
  or unit.
- **FR-003**: A **once** schedule MUST run exactly one time, at the chosen date and time (within one
  heartbeat cycle), and MUST NOT run again afterward.
- **FR-004**: After a once schedule has fired, the system MUST mark it as completed/inactive so the
  heartbeat never triggers it again, while keeping it visible in the schedule list with its status.
- **FR-005**: A once schedule whose chosen date/time is in the past at save time MUST be rejected with
  a clear, inline validation message, and no schedule created.
- **FR-006**: For an **interval** schedule, the operator MUST set a positive whole number and choose a
  unit from a drop-down offering exactly: minute, hour, day, week, month; an interval schedule MUST
  NOT ask for an absolute clock time.
- **FR-007**: The interval unit drop-down MUST present all five units in Ukrainian.
- **FR-008**: An interval schedule MUST run every N units repeatedly, computing each next run one
  further interval ahead of the last.
- **FR-009**: Interval computation MUST handle the month unit as a calendar month (same day-of-month
  and time one month later), degrading gracefully for days that do not exist in the target month.
- **FR-010**: An interval whose count is zero, negative, empty, or not a whole number MUST be rejected
  with a clear, inline validation message.
- **FR-011**: All new or changed scheduling UI text MUST be in Ukrainian, consistent with the existing
  single-locale catalog.
- **FR-012**: Validation errors for schedule creation/editing MUST be shown inline on the form, not as
  a generic browser alert or an Internal Server Error page.
- **FR-013**: Existing schedule behavior MUST be preserved: each schedule carries its own target and
  optional label, a profile may have multiple schedules, schedules can be enabled/disabled and
  deleted, overlap and catch-up policies continue to apply, a schedule can be created from a past run
  in history, and every schedule change is recorded in the audit log.
- **FR-014**: The change MUST NOT break the standalone credential-tool scheduled tasks, which share
  the same scheduling engine; recurrences those tasks already use MUST continue to function.
- **FR-015**: The change MUST introduce no new runtime dependency and MUST operate fully offline,
  consistent with the air-gapped deployment.
- **FR-016**: Operators MUST be able to edit an existing schedule from the schedule list — changing its
  recurrence (once or interval, including switching kinds), target, label, and enabled state — reusing
  the same form controls as creation, with the form pre-populated from the schedule's current values.
- **FR-017**: Saving an edit MUST update the schedule in place (no duplicate created), recompute its
  next run from the new recurrence, validate it identically to creation (inline errors, no change on
  failure), and record the change in the audit log.

### Key Entities *(include if feature involves data)*

- **Schedule recurrence**: The rule describing when a schedule runs, of one of two kinds:
  - *once* — a single absolute date and time (day, hour in 24h, minute); non-repeating.
  - *interval* — a positive count plus a unit (minute, hour, day, week, month); repeating.
  Stored as structured data on the existing schedule record (no change to the set of stored fields is
  expected; completion of a once schedule reuses the existing enabled/last-run state).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator can create a one-time schedule for a chosen future date and 24-hour time; it
  runs once within one heartbeat cycle of that time and never runs again (afterward it shows as
  completed).
- **SC-002**: An operator can create a recurring schedule by entering a number and selecting one of
  the five units; it runs repeatedly on that cadence.
- **SC-003**: On the create-schedule form, "once" appears above "interval", the once inputs are
  ordered day → hour (24h) → minute, and the interval unit drop-down shows all five units in
  Ukrainian.
- **SC-004**: A past once time and a non-positive/non-integer interval are each rejected with a clear
  message shown inline, with no schedule created and no server error page.
- **SC-005**: Existing standalone credential-tool scheduled tasks continue to run unchanged after this
  feature ships.
- **SC-006**: All existing automated tests for prior features (001, 002, 003) continue to pass, and
  the new behavior is covered by tests.
- **SC-007**: An operator can edit any schedule in the list (recurrence, target, label, enabled),
  save, and see the row updated in place with a recomputed next run — without deleting and recreating
  it; invalid edits are rejected inline and leave the schedule unchanged.

## Assumptions

- **Replacing daily/weekly**: The previous "daily (hour:minute)" option (and the unused "weekly"
  option) are **removed from the discovery-schedule UI**, superseded by *once* (for a specific
  date/time) and *interval* (for a cadence). A recurring scan at a fixed wall-clock time every day is
  approximated by "every 1 day" (which recurs 24h after each run rather than at a fixed clock time);
  this is acceptable for scan cadence. If fixed-clock-time daily recurrence turns out to be required,
  it can be revisited — flagged here for the operator to object before planning.
- **Time zone**: A once date/time is entered and shown in the operator's local time (the same time
  zone the rest of the UI displays), and the system fires the run at that wall-clock time; the
  handling is consistent end to end so the operator sees the run happen when they expect.
- **No schema change expected**: Recurrence is already stored as structured JSON on the schedule
  record, and once-completion reuses the existing enabled/last-run fields, so this feature is not
  expected to require a database migration. (If the plan finds one is needed, it will follow the
  schema-upgrade mechanism from feature 004.)
- **Shared engine extended, not forked**: The single scheduling engine is extended to understand the
  once and unit-based-interval recurrences; it keeps accepting any recurrence shapes already in use by
  the credential-tool tasks for backward compatibility. A single scheduler continues to serve both
  (per the project's simplicity principle).
- **Heartbeat granularity**: Runs fire on the existing periodic heartbeat (currently ~30s), so "runs
  at time T" means "within one heartbeat cycle of T", which is the established behavior.
- **Scope**: This feature changes the discovery-schedule form and the shared recurrence model. Redoing
  the credential-tool task UI to expose the same once/interval controls is out of scope (that UI keeps
  working as-is); it may adopt the new controls in a later feature.

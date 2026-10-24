# Feature Specification: Credential-Check Tool Fixes

**Feature Branch**: `008-credential-tool-fixes`

**Created**: 2026-10-23

**Status**: Draft

**Input**: User bug report after testing the credential-check tab — broken "once"
scheduling, missing/incorrect schedule columns, no credential-dictionary
selection, HTTP/HTTPS probes that fetch the login page instead of
authenticating, a 3-attempt cap that should become "try the whole dictionary",
runs that only appear in history after they finish, a weak result window, no
stop-on-match, and two layout refinements.

## Clarifications

### Session 2026-10-23

- Q: How should the HTTP/HTTPS probe authenticate, given the target uses a form
  login (`POST /login → 401/200`) rather than HTTP Basic auth? → A: Form-aware
  flow — (1) a quick GET fingerprints the form/CMS type by signature, (2) an
  appropriate settings dictionary is selected from the pool, (3) a POST submits
  the default username/password pair, (4) the response is validated against
  success criteria (status code **and** body content). HTTPS uses the same
  mechanism and ignores self-signed certificates.
- Q: The constitution pins a NON-NEGOTIABLE 3-attempt cap to avoid device
  lockout — how to reconcile with "try all credentials"? → A: Amend the
  constitution (done, v2.0.0): Principle III's fixed 3-attempt cap becomes an
  **operator-configurable per-target ceiling that defaults to the selected
  dictionary's size**, so by default every credential in the chosen dictionary
  is tried once. The ≥5-second cooldown stays NON-NEGOTIABLE, central
  enforcement and stop-on-match are retained, and an operator may still set a
  lower ceiling (which re-enables `inconclusive`).
- Q: The result window should highlight the credential that worked, but FR-039
  forbids persisting an attempted secret — how much to reveal? → A: Highlight by
  **username only** (plus which dictionary/entry matched). The matched
  **password is never displayed or persisted**; the audit log stays secret-free.
- Q: How should a run show as "running" immediately instead of only after it
  finishes? → A: Execute the check on a **background thread** (as discovery scans
  do); the run row is committed as `running` at once and the UI **polls** for
  status until it completes.

## Assumptions

- "Dictionary" (dict) = one `DefaultCredentialEntry` row: a named, per-service
  list of default `username`/`secret` pairs plus its success keywords and (new)
  HTTP form-probe settings.
- The attempt ceiling is now **operator-configurable, defaulting to the selected
  dictionary's size** (constitution v2.0.0 amendment of Principle III, authorized
  by the project owner). The ≥5-second cooldown remains NON-NEGOTIABLE and
  un-waivable. The audit log continues to record attempt counts and timings so
  the cooldown remains verifiable.
- A username is not a secret and may be stored/shown; the attempted/ matched
  **password** remains governed by FR-039 and is never persisted or shown.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Correct, scan-parity scheduling (Priority: P1)

As a Network Systems Administrator scheduling a credential check, I want the
same "once / interval" scheduler the scan scheduler has, and a task table that
honestly tells me whether a task is enabled and when it next runs, so that a
one-time check actually runs once and I can read the schedule at a glance.

**Why this priority**: Scheduling is visibly broken today (a "once" selection is
stored/shown as an interval), which undermines trust in the whole tab.

**Independent Test**: Create a "once" task with a future date/time and confirm it
is stored and displayed as a one-time task (not an interval); confirm the task
table shows an "enabled" column and a "next check time" column.

**Acceptance Scenarios**:

1. **Given** the schedule form, **When** the operator selects "Одноразово"
   (once), fills a future date/hour/minute, and submits, **Then** the task is
   created with a `once` recurrence and the table shows it as one-time with its
   absolute next-run instant — never as an interval. *(3.1.1)*
2. **Given** the task table, **When** it renders, **Then** it includes an
   **Enabled** column reflecting each task's enabled flag. *(3.1.2)*
3. **Given** the task table, **When** it renders, **Then** the former
   "Періодичність" (period) column is replaced by a **Next check time** column
   showing the task's `next_run_at`. *(3.1.3)*
4. **Given** an existing task, **When** the operator edits it, **Then** the form
   pre-selects the correct kind (once/interval) and its fields round-trip
   without converting once→interval.
5. **Given** a past date/time on a "once" task, **When** the operator submits,
   **Then** the request is rejected with a field-level validation message
   (parity with scan schedules).

---

### User Story 2 - Choose which credential dictionary to use (Priority: P1)

As an administrator, I want to pick a specific credential dictionary when I run
or schedule a check (not implicitly test every dictionary for the service), so I
control exactly which default-credential set is attempted against a device.

**Why this priority**: Required for the new "try the whole dictionary" semantics
to be meaningful and bounded — the operator must choose the dictionary whose
entries will be exhausted.

**Independent Test**: With two dictionaries defined for a service, start a run
selecting one of them and confirm only that dictionary's credentials are tried.

**Acceptance Scenarios**:

1. **Given** at least one dictionary exists for the selected service, **When**
   the operator opens the run or schedule form, **Then** a dictionary selector
   lists the dictionaries available for that service. *(3.2)*
2. **Given** a selected dictionary, **When** the check runs, **Then** only that
   dictionary's credentials are attempted.
3. **Given** the service selection changes, **When** the form updates, **Then**
   the dictionary selector refreshes to the dictionaries for the new service.
4. **Given** no dictionary exists for the service, **When** the operator tries to
   run, **Then** a clear message explains a dictionary must be created first.

---

### User Story 3 - HTTP/HTTPS probes that actually authenticate (Priority: P1)

As an administrator, I want the HTTP and HTTPS checks to submit credentials to
the device's login form and judge the real outcome, so a result reflects whether
default credentials were accepted — not merely that a login page loaded.

**Why this priority**: The current probe produces false results (it only GETs the
login page), making HTTP/HTTPS compliance findings meaningless.

**Independent Test**: Point an HTTP check at a form-login test server; confirm the
probe issues a `POST` to the login path and that a wrong credential yields a
"rejected" (401-equivalent) outcome and a correct one yields "accepted".

**Acceptance Scenarios**:

1. **Given** an HTTP target with a form login, **When** the probe runs, **Then**
   it first issues a GET to fingerprint the form type, then **POSTs** the
   credential to the login path (not a bare GET of `/`). *(3.3.1)*
2. **Given** the login POST response, **When** it is evaluated, **Then** success
   is determined by configured criteria combining **status code and body
   content**, so a `401` is a rejection and an accepted login is distinguished
   from the login page itself.
3. **Given** an HTTPS target with a self-signed certificate, **When** the probe
   runs, **Then** it uses the same POST mechanism over TLS and **does not fail on
   certificate validation** (self-signed certs are tolerated). *(3.3.2)*
4. **Given** a dictionary with HTTP form settings (login path, HTTP method,
   username/password field names, success/failure criteria, optional fingerprint
   signatures), **When** a probe runs, **Then** it uses those settings; sensible
   defaults apply when a field is omitted.
5. **Given** a login form that issues a CSRF/anti-forgery token on the initial
   GET, **When** the probe submits the POST, **Then** it carries the token
   captured from that GET where the dictionary's settings declare one. *(nice to
   have; may be deferred if the target doesn't require it)*

---

### User Story 4 - Exhaustive, cooldown-guarded attempts (Priority: P1)

As an administrator auditing for default credentials, I want the check to try
every credential in the chosen dictionary (one every ≥5 seconds) and stop the
moment one works, so I get a complete yet device-safe audit.

**Why this priority**: The 3-attempt cap previously left dictionaries largely
untested, producing "inconclusive" results; the operator wants full coverage.

**Independent Test**: With a dictionary of N credentials where the k-th is valid,
confirm exactly k attempts are made (stop-on-match) and that a ≥5s cooldown
separated consecutive attempts; with none valid, confirm all N were tried.

**Acceptance Scenarios**:

1. **Given** a chosen dictionary and the default ceiling, **When** a check runs
   and no credential matches, **Then** every credential in the dictionary is
   attempted (ceiling = dictionary size). An operator-set lower ceiling caps
   attempts below that. *(3.3)*
2. **Given** consecutive attempts, **When** they execute, **Then** at least 5
   seconds separate them (cooldown retained). *(constitution Principle III)*
3. **Given** a credential is accepted mid-dictionary, **When** the match occurs,
   **Then** the check **stops immediately** for that target and does not try the
   remaining credentials. *(3.6)*
4. **Given** every credential was tried and none matched, **When** the run
   finishes, **Then** the target is reported **compliant** (no longer
   "inconclusive", since the dictionary is now fully exhausted).

---

### User Story 5 - Live run status (Priority: P2)

As an administrator, I want a started check to appear in history immediately with
a "running" status, so I can see work in progress instead of waiting blindly for
it to finish.

**Why this priority**: With exhaustive attempts and 5s cooldowns a run can take
minutes; a synchronous, invisible run is a poor experience.

**Independent Test**: Start a run against several targets; confirm it appears in
history as `running` right away and transitions to `completed` without a manual
refresh.

**Acceptance Scenarios**:

1. **Given** the operator starts a run, **When** the request returns, **Then** the
   run already exists in history with status `running`. *(3.4)*
2. **Given** a running check, **When** it finishes on its background thread,
   **Then** the history/result view reflects `completed` via polling without a
   full page reload.
3. **Given** a running check, **When** the operator opens its result window,
   **Then** partial progress is shown and the view keeps polling until done.

---

### User Story 6 - Rich result window (Priority: P2)

As an administrator reading a check result, I want a per-attempt table (like a
scan result) showing each attempt's username, the device's response, and the
outcome, with the successful row highlighted, so I can see exactly which default
credential a device accepted and act on it.

**Why this priority**: The current `alert()` of one line per host is unusable for
diagnosis; this is the payoff screen of the whole tool.

**Independent Test**: Run a check that accepts the k-th credential; open the
result window and confirm a table lists attempts with usernames, responses, and
results, and that the matching row is highlighted.

**Acceptance Scenarios**:

1. **Given** a completed (or running) check, **When** the operator opens its
   result, **Then** a result page/window shows a table of attempts with columns
   for target, **username** tried, response (status/excerpt), and result —
   styled like the scan result page, not a browser `alert`. *(3.5)*
2. **Given** a credential matched, **When** the table renders, **Then** the
   matching row is **highlighted** and labelled by username and dictionary
   entry. *(3.5)*
3. **Given** any attempt, **When** it is displayed or stored, **Then** the
   attempted/matched **password never appears** in the table, the stored result,
   or the audit log. *(FR-039)*
4. **Given** a running check, **When** the result window is open, **Then** it
   updates as attempts complete (shares US5's polling).

---

### User Story 7 - Run form & dictionary layout polish (Priority: P3)

As an administrator, I want the "run now" controls arranged on two rows and the
dictionary description field made wide, so the form is compact and the
description is comfortable to edit.

**Why this priority**: Pure usability polish; independent of behavior.

**Independent Test**: Open the credential tab; confirm the run form shows the
target on the top row and port + service + dictionary + start button together on
a second row, and that the dictionary description input spans the available
width.

**Acceptance Scenarios**:

1. **Given** the "run now" card, **When** it renders, **Then** the **target**
   field occupies the first row and **port, service, dictionary, and the start
   button** share one row beneath it. *(3.7)*
2. **Given** the dictionary form, **When** it renders, **Then** the
   description/vendor field is a **wide** input using the available width. *(3.8)*

---

### Edge Cases

- A dictionary is deleted while a run referencing it is in flight → the run uses
  the credentials snapshotted at start; deletion does not abort it.
- HTTP target is unreachable / times out → the attempt is recorded as an error
  outcome, counts toward pacing, and the run still completes.
- A very large dictionary → exhaustive attempts at ≥5s each can make a run long;
  this is expected and surfaced by the running status (US5). *(No new upper
  bound is imposed, per the cap decision; operators choose dictionary size.)*
- `once` task whose moment passed while the app was down → unchanged from the
  shared scheduler's existing catch-up/one-shot handling.
- Background worker crash mid-run → the run must not remain stuck `running`
  forever; it is marked `failed` with an error detail (parity with scans).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-101 (Scheduling parity)**: The credential-task scheduler MUST offer the
  same recurrence kinds as scan schedules (`once`, `interval` with
  every/unit), building/storing/editing them identically; a `once` selection
  MUST persist and display as one-time. *(3.1, 3.1.1)*
- **FR-102 (Task table columns)**: The task table MUST show an **Enabled**
  column and a **Next check time** column, replacing the raw recurrence/period
  column. *(3.1.2, 3.1.3)*
- **FR-103 (Recurrence validation)**: Creating/updating a task MUST validate the
  recurrence (reject a past `once`, non-positive interval, etc.) with
  field-level errors, matching scan-schedule behavior.
- **FR-104 (Dictionary selection)**: Run-now and task forms MUST let the operator
  select one credential dictionary for the chosen service, and the check MUST
  attempt only the selected dictionary's credentials. *(3.2)*
- **FR-105 (HTTP form probe)**: The HTTP/HTTPS probe MUST authenticate via a
  form flow: GET to fingerprint, select settings, POST the credential to the
  configured login path, and validate the response by **status code and body
  content**. It MUST NOT conclude from a bare GET of `/`. *(3.3.1)*
- **FR-106 (HTTPS self-signed)**: The HTTPS probe MUST reuse the HTTP form
  mechanism over TLS and MUST tolerate self-signed/invalid certificates without
  failing the attempt. *(3.3.2)*
- **FR-107 (Dictionary HTTP settings)**: A dictionary MUST be able to carry HTTP
  form-probe settings (login path, method, username/password field names,
  success/failure criteria, optional fingerprint signatures, optional CSRF token
  field), with sensible defaults when unset.
- **FR-108 (Configurable ceiling, exhaustive default)**: The per-target attempt
  ceiling MUST be operator-configurable and MUST default to the chosen
  dictionary's size, so by default every credential is tried unless a match
  occurs. The check MUST NOT exceed the effective ceiling. *(3.3; constitution
  III v2.0.0)*
- **FR-109 (Cooldown retained, non-negotiable)**: Consecutive attempts against a
  target MUST be separated by at least the configured cooldown (≥5 seconds),
  which cannot be shortened or waived. *(Principle III)*
- **FR-110 (Stop on match)**: A check MUST stop attempting further credentials
  against a target as soon as one is accepted. *(3.6)*
- **FR-111 (Exhausted ⇒ compliant)**: When all dictionary credentials are tried
  and none match, the target MUST be reported **compliant** (not inconclusive).
- **FR-112 (Immediate running status)**: Starting a run MUST create and persist
  the run as `running` before probing begins, executing probes on a background
  worker; the UI MUST poll until the run is `completed`/`failed`. *(3.4)*
- **FR-113 (Result window)**: The result view MUST present a per-attempt table
  (target, username, response status/excerpt, result) styled like the scan
  result page, with the matching attempt highlighted. *(3.5)*
- **FR-114 (Username-only disclosure)**: The matching credential MUST be
  identified by **username** (and dictionary entry) only. The attempted/matched
  **password MUST NOT be displayed or persisted** anywhere (result rows, run
  record, audit log). *(3.5, FR-039)*
- **FR-115 (Run-form layout)**: The run-now controls MUST be laid out as target
  on row one; port, service, dictionary, and start on row two. *(3.7)*
- **FR-116 (Dictionary description width)**: The dictionary description/vendor
  field MUST be a wide, full-width input. *(3.8)*
- **FR-117 (Failure handling)**: A background run whose worker fails MUST be
  marked `failed` with an error detail and MUST NOT remain stuck `running`.

### Device-Safety & Auditability Invariants (retained)

- The ≥5-second cooldown between attempts (Principle III) is unchanged.
- The audit log and stored results continue to record attempt counts, timings,
  protocol, and **usernames only** — never an attempted/matched password
  (FR-039, constitution Principle IV).

### Key Entities

- **Credential dictionary** (`DefaultCredentialEntry`, extended): per-service
  named list of `{username, secret}` pairs, success keywords, and new HTTP
  form-probe settings. Selectable per run/task.
- **Tool task** (`ToolTask`, extended): gains a reference to the chosen
  dictionary; recurrence supports once/interval as scans do.
- **Tool check run / result** (`ToolCheckRun` / `ToolCheckResult`, extended):
  run carries live `running` status from the background worker; results carry a
  per-attempt list (username, response summary, matched flag) for the result
  table — password-free.

## Success Criteria *(mandatory)*

- **SC-001**: A "once" task created through the UI is stored and shown as a
  one-time task 100% of the time (no once→interval conversion).
- **SC-002**: The task table shows enabled state and next-check time for every
  task.
- **SC-003**: An HTTP/HTTPS check against a form-login target issues a POST and
  correctly distinguishes accepted vs rejected credentials (verified against the
  target's own logs showing `POST /login` with 200 vs 401).
- **SC-004**: With a dictionary of N credentials and the k-th valid, exactly k
  attempts occur, spaced ≥5s, and the run stops at k.
- **SC-005**: A started run appears in history as `running` within one UI poll
  interval and transitions to `completed` without manual refresh.
- **SC-006**: The result window shows a per-attempt table with the matching row
  highlighted by username, and no password text appears anywhere in the UI,
  stored records, or audit log.
- **SC-007**: The run form and dictionary form match the requested layout (target
  row + combined controls row; wide description field).

## Out of Scope

- Non-HTTP protocol probe rewrites (SIP/SSH/Telnet/FTP/RouterOS) beyond what the
  shared attempt-loop changes (cap/stop-on-match/per-attempt records) require.
- Credential brute-forcing beyond the operator-provided dictionaries.
- Any change that would persist or reveal attempted passwords.

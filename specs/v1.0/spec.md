# Feature Specification: Milmap v1.0 — Asset Inventory & Compliance Management Dashboard (Consolidated)

**Spec ID**: `v1.0-milmap`

**Created**: 2026-10-24

**Status**: Consolidated baseline (supersedes the per-feature drafts for the purpose of describing the shipped product)

**Consolidates**: features `001`–`010` and Constitution **v2.0.0**

**Input**: This specification merges every requirement, clarification, and
course-correction accumulated across ten incremental features into a single,
final-state description of what Milmap is and must do. Where a later feature
superseded an earlier decision, **only the final decision is stated here**; the
superseded wording is recorded once in *Evolution & Key Corrections* so the
reasoning is not lost.

---

## 1. Context & Scope

Milmap is an **internal, air-gapped, local web application** used by an
organization's own **Network Systems Administrators** to (a) inventory internal
infrastructure and (b) audit its security-compliance posture. It is a
**defensive network-administration tool** operated only against the
organization's own, authorized assets on an isolated network with **no internet
access at install time or runtime**.

Its purpose is asset-inventory and security hygiene: knowing what is on the
network, which services and firmware versions are running, and whether any
device is still outdated or exposed with factory-default credentials. Because
the environment is air-gapped, **every reference dataset is maintained and
updated offline, inside the deployment**.

`nmap` appears by name throughout because the project owner designated it as the
underlying telemetry tool (a domain dependency), not because the UI chose it.
NSE script identifiers (e.g. `mikrotik-routeros-version`) appear for the same
reason.

**Scale (v1):** a medium environment — overall inventory up to ~5,000 hosts; a
single run may cover one or more /24–/22 subnets (up to ~1,024 addresses per
/22). A few operators may act concurrently. Larger, multi-site deployments are
out of scope for v1.

---

## 2. Evolution & Key Corrections (what changed and why)

This section is the record of the **blind spots, corrections, and desires**
surfaced during development. Each item is the *final* decision; earlier wording
it replaced is noted so the intent is traceable.

1. **Product renamed to "Milmap"** (was "Asset Inventory & Compliance
   Management Dashboard" in the UI). Underlying data was retained — a rename,
   not a migration. *(002)*
2. **UI is a single dark theme in Ukrainian**, later evolved into a full
   **tactical-HUD visual language** (amber-on-near-black, Volja wordmark,
   bracketed/notched panels, ambient HUD decoration) applied across every
   screen. Technical identifiers (`T3`, `-sV`, ports, NSE names) stay in English.
   Every config control carries a `?` inline help annotation. *(002 → 010)*
3. **Two roles, not one.** Feature 001 assumed every operator was an
   administrator; 002 introduced exactly **Administrator** and **Operator** (no
   read-only viewer). The first account on a fresh install is Administrator;
   later accounts default to Operator. *(001 assumption → 002, Constitution
   Principle VII)*
4. **Host-management link removed** from profiles and the results table,
   including all `{host}` placeholder handling (was 001 FR-013/FR-019). Planned
   to return later as a separate standalone function; out of scope for v1. *(002)*
5. **Default-credential check decoupled from discovery profiles** into a
   **standalone tool** that runs on demand or on its own schedule. A discovery
   profile's run never performs the credential check. *(001 US6 → 002 US5)*
6. **Full operator control of the scan command.** "Extract open ports" and
   "extract service/firmware version" became independent, non-mandatory toggles;
   new profiles default to timing template `T3` (operator-changeable T0–T5); the
   operator can preview the **exact effective command**; the command is composed
   **only from a vetted allow-list** — never a raw/free-form flag string. NSE
   scripts are selectable from an Administrator-maintained allow-list. *(002)*
7. **Home page redesigned.** The compliance-only landing panel (empty whenever
   no profile had version evaluation) was replaced by a useful **"Головна"**
   home: 5 most-recently-updated profiles (each runnable) and the 20 most-recent
   scans across *all* profiles, plus the soonest-firing scheduled tasks, in a
   two-column layout. Compliance posture is shown where evaluated and
   "not applicable" otherwise. *(003 → 006)*
8. **Dynamic UI** — lists update after a mutation (create/edit/duplicate/delete)
   without a manual browser reload. *(003)*
9. **Results table correctness.** Small scans (≤10 ports in the *results*) show
   every scanned port with its state; large scans (>10) show only open ports; a
   filtered/closed port is never shown as open; a responding host with no open
   ports in a large scan shows "Всі порти closed або filtered". Service version
   is read from an open port only. *(003)*
10. **Non-compliant rows are actionable** — highlighted orange and showing the
    expected/target version, not just the word "non-compliant". *(003)*
11. **Profile-scan scheduling added.** Previously only the credential tool could
    be scheduled. A schedule is an independent task that *references* a profile,
    carries **its own target** (so target-less profiles are schedulable), and a
    profile may have multiple schedules. One shared scheduling engine serves both
    profile scans and tool tasks. *(003, Constitution Principle VI)*
12. **Target-less profiles** — a profile may be saved without a target; the
    target is supplied at launch (used for that run only, never persisted back).
    *(003)*
13. **Reference-versions dictionary is in-app editable** by both Operators and
    Administrators, with every edit audited. *(003)*
14. **Reliable in-place database upgrades.** A real production break (creating a
    schedule 500'd, the scheduler heartbeat crashed every ~30s with
    `no such column: schedules.target_scope`) exposed that there was no migration
    path. v1 ships a versioned-migration mechanism: one documented offline
    upgrade step, a pre-upgrade recovery copy, idempotency, a per-database schema
    stamp, and startup **fail-fast** on a schema/code mismatch (no silent serving,
    no heartbeat traceback flood). *(004)*
15. **Schedule recurrence redesigned** to **once** and **interval** ("every N ×
    minute/hour/day/week/month"). "Once" is listed above "interval"; its inputs
    are ordered day → hour (24h) → minute; a past "once" time is rejected inline.
    The legacy `daily`/`weekly` clock-time shapes were removed from the discovery
    UI (still understood by the shared engine for back-compat). Schedules are
    editable in place. *(005)*
16. **UI layout refinements** — removed redundant headings/columns (profiles'
    "Розклад", history's "З кешу?", several compliance columns on Home), moved
    the version dictionary into a role-aware **Configuration** split into subtabs
    (Акаунт / Бібліотека), kept the command preview visible without a target,
    made the ports field show its full contents. *(006)*
17. **Version compliance model replaced.** Instead of enumerating every valid and
    invalid version, the dictionary now records only a **minimum-acceptable
    (current) version threshold** per product: below the threshold is
    non-compliant, at/above is compliant, no threshold is unknown. SemVer-style
    ordering. **Historical verdicts are immutable** — each scan freezes its
    verdict and the checked version; raising a threshold later never rewrites
    history. *(007)*
18. **Automated version ingestion (offline-safe).** An out-of-runtime staging
    fetcher runs on an internet-connected machine, pulls current versions from
    vendor sites, and emits a signed/integrity-checked **bundle**. The air-gapped
    app only verifies and imports the bundle (preview diff → apply), recording
    provenance and an audit event. **The running app makes no outbound request.**
    *(007)*
19. **Credential check, the device-safety invariant, redefined.** The fixed
    **3-attempt cap** became an **operator-configurable per-target ceiling that
    defaults to the selected dictionary's size** — so by default every credential
    in the chosen dictionary is tried once, with **stop-on-match**. The
    **≥5-second cooldown remains NON-NEGOTIABLE** and un-waivable. Exhausting the
    dictionary with no match is **compliant**; a ceiling set below the dictionary
    size that prevents a conclusive result is **inconclusive**. This was ratified
    as **Constitution v2.0.0** (MAJOR). *(008, Constitution III)*
20. **Credential tool fixes.** Scheduling reached scan-parity (once/interval, an
    Enabled column, a Next-check-time column); a **dictionary selector** per
    run/task; **HTTP/HTTPS probes now authenticate** via a form flow (GET to
    fingerprint → POST the credential → judge by status **and** body), tolerating
    self-signed TLS; runs show as **running immediately** on a background worker
    and the UI polls; a **rich per-attempt result table** highlights the matching
    row **by username only** (the password is never shown, stored, or logged). *(008)*
21. **Results → host pivot + Scan Configuration window.** Operators can tick host
    rows (or auto-select invalid-version hosts) and pivot them into a credential
    check or into a new scan with a chosen profile. The jarring `window.prompt`
    for a launch-time target is replaced by a **Scan Configuration window**
    (profile-editor-like, with a command preview and a Start Scan button) for
    *every* Run now; one-off adjustments never write back to the profile. *(009)*

---

## 3. Consolidated Clarifications (resolved decisions)

- **Credential check is a real, bounded authentication attempt**, confirmed by a
  response-**body** signature match (not merely a protocol status). *(001)*
- **Attempt ceiling** is operator-configurable, default = selected dictionary
  size; **cooldown ≥5s is non-negotiable**; **stop-on-match**; exhausted ⇒
  compliant; capped-short ⇒ inconclusive. *(008, Constitution III)*
- **Matched credential disclosure**: username (and dictionary entry) only; the
  password never appears in the UI, stored record, or audit log. *(008)*
- **Scale**: ~5,000 hosts; a run may cover a /22 (~1,024 addresses). *(001)*
- **Concurrency**: a few operators; detect conflicting profile edits (no silent
  overwrite) and prevent duplicate concurrent runs of the same profile/task. *(001)*
- **Scan-size threshold** counts the actual ports present in a run's results
  (not the profile's port spec); ≤10 = small, >10 = large. *(003)*
- **Home recent-scans** shows the 20 newest across all profiles, newest first;
  recent-profiles shows 5; scheduled tasks show 5 ordered by soonest next-run. *(003, 006)*
- **Reference versions** are viewable AND editable in-app by Operators and
  Administrators; edits are audited as configuration changes. *(003)*
- **Profile scheduling**: a schedule references a profile and carries its own
  target; a profile may have multiple; schedulable even when target-less. *(003)*
- **Version ordering**: SemVer-style — numeric segments left-to-right, missing
  trailing segments = 0 (`9.0`=`9.0.0`), a pre-release/suffix sorts below the
  same base (`9.0-rc1` < `9.0`); unorderable/mixed-scheme ⇒ unknown. *(007)*
- **Bundle integrity** is verified before any threshold changes; failure rejects
  the bundle with no change; human review/apply is separate and additional. *(007)*
- **Immutable history**: verdicts and checked versions are frozen per scan and
  never recalculated on later threshold/setting changes. *(007)*
- **HTTP/HTTPS probe** uses a form flow (GET fingerprint → POST credential →
  status + body), tolerant of self-signed certs. *(008)*
- **Live status**: a started check is committed as `running` and executed on a
  background worker; the UI polls to completion. *(008)*
- **Pivot presentation**: pivot actions navigate to the destination tool page
  with the target pre-filled; selection need not survive the navigation;
  invalid-version auto-select unions with an existing manual selection. *(009)*
- **Scan Configuration window** edits only target, ports, timing, and extracted
  fields for one run; compliance toggle and NSE selection are inherited
  read-only; nothing writes back to the saved profile. *(009)*

---

## 4. User Scenarios & Testing

Priorities (P1 highest) reflect the consolidated product; each story is
independently testable.

### Area A — Authentication & Access (P1)

**A1 — Secure local access.** No page, data, or action is reachable while signed
out. Passwords must be ≥20 characters at creation and change. Repeated failures
are throttled/locked and audited. Idle sessions expire. *(001 US1)*

**A2 — Roles & user management.** Any operator can change their own password. An
Administrator can create, edit, deactivate, assign roles to, and reset passwords
for other accounts. The first account on a fresh install is Administrator; later
accounts default to Operator. The deployment can never be left with no active
Administrator, and the password floor can never be set below 20. *(002 US3)*

**Acceptance (representative):**
1. An unauthenticated request to any page redirects to sign-in; no data leaks.
2. A password < 20 chars is rejected at creation and change with a clear reason.
3. After N consecutive failures sign-in is throttled/blocked and audited.
4. An Administrator creating an Operator → that user can change only their own
   password; attempts at user management / security settings / allow-list are
   denied server-side. Deactivation/reset invalidates the user's session at next
   action.
5. Deactivating or demoting the last Administrator is prevented.

### Area B — Discovery Profiles & Execution (P1)

**B1 — Profile CRUD & full command control.** Create/view/edit (via an Edit
button)/duplicate/delete profiles. A profile captures target scope (hosts/
ranges/subnets, **optional**), port/service selection, timing template (default
`T3`, changeable T0–T5), independent extract-open-ports / extract-service-version
toggles, and selected NSE scripts from the allow-list. The operator previews the
**exact effective command**; the command is composed only from vetted options —
never a raw flag string. Concurrent edits are conflict-protected (no silent
overwrite). *(001 US2, 002 US1/US2/US4)*

**B2 — Run & review results.** Run on demand; progress and completion are shown;
an in-progress run can be cancelled (recorded cancelled, partial results kept).
Results list each responding host with the selected telemetry and per-host NSE
output. Port column adapts to scan size; non-compliant rows are orange with the
target version; empty vs failed runs are distinct. *(001 US3, 002, 003 US3/US4)*

**B3 — Scan Configuration window.** Every **Run now** opens a profile-editor-like
window pre-filled from the profile, editing only target/ports/timing/extracted
fields for that run, with a live command preview and a **Start Scan** button.
Target-less profiles block Start Scan until a valid target is entered. Nothing
writes back to the profile; the legacy browser prompt is gone. *(009 US1)*

**Acceptance (representative):**
1. Toggling each extraction option and changing timing yields a valid saveable
   profile (including open-ports-only and none); the preview matches exactly.
2. Edit updates in place (no duplicate); a later save over a changed profile is
   rejected/flagged.
3. Small scan (≤10 ports) shows each port's state; large scan shows only open;
   a filtered/closed port is never shown as open; host-up-no-open-ports shows the
   defined text.
4. Run now opens the Scan Configuration window; Start Scan on a target-less
   profile is blocked until a valid target is supplied.

### Area C — History, Caching & Dynamic UI (P2)

**C1 — History & caching.** Every run is persisted (timestamp, profile,
parameters, status, full results) and listed newest-first; any run opens to its
captured results. Recent results within a freshness window can be reused (labeled
cached, with original time); "force fresh" overrides. A configurable retention
policy applies predictably. Deleting a profile keeps its historical runs. *(001 US4)*

**C2 — Dynamic UI.** After a user-initiated mutation (create/edit/duplicate/
delete), the affected list updates without a manual reload; a failed mutation
leaves the view consistent with server state and signals the error. *(003 US2)*

### Area D — Home Dashboard (P1)

**D1 — Useful Home ("Головна").** Two-column layout: recent profiles (5, each
runnable) and soonest scheduled tasks on the left; the 20 most-recent scans
across all profiles on the right. Compliance posture is shown where evaluated and
"not applicable" otherwise; the page is never empty when profiles exist. Clicking
a scheduled task opens the Schedules page. *(003 US1, 006 US1/US2)*

### Area E — Scheduling (P2)

**E1 — Profile-scan & tool scheduling on one engine.** Create recurring/one-time
schedules for discovery profiles and for the credential tool. A schedule
references a profile (or targets the tool), carries its own target and optional
label, and a profile may have several. Schedules can be enabled/disabled, edited
in place, and created from a past run in history (prefilling profile/target/
parameters). Next-run is displayed; overlap and catch-up policies apply; no
duplicate concurrent runs. *(001 US5, 002 US5, 003 US6, 005)*

**E2 — Once / interval recurrence.** "Once" (listed first): a calendar day + hour
(0–23) + minute; runs exactly once then shows completed; a past time is rejected
inline. "Interval": a positive whole number + unit drop-down (minute/hour/day/
week/month, in Ukrainian); recurs every N units; month roll-over handled
gracefully; non-positive/non-integer rejected inline. *(005 US1–US4, 008 US1)*

### Area F — Compliance: Version Validity (P1)

**F1 — Minimum-version-threshold compliance (offline).** Each product has a
minimum-acceptable (current) version threshold. Detected version below → **non-
compliant** (orange, shows the upgrade target); equal/above → **compliant**; no
threshold → **unknown**; unorderable/mixed-scheme → **unknown**. Multiple
recorded versions → the **minimal** is the threshold. **Zero network lookups.**
Verdicts are **immutable history**. *(001 US6, 003 US4, 007 US1)*

**F2 — Maintain thresholds in the library.** Operators and Administrators record/
edit/remove thresholds in Configuration → Бібліотека; edits are audited and take
effect for subsequent evaluations. Legacy enumerated data is migrated (lowest
`valid` version becomes the threshold; invalid-only products surfaced for review).
*(003 US4, 006 US5, 007 US2)*

**F3 — Automated ingestion (staging fetcher + signed bundle).** An Administrator
defines tracked entries (vendor, official source URL, models). A **separate
staging fetcher** (internet-connected machine, never imported by the app) emits a
per-vendor **bundle** with an integrity/authenticity check. The air-gapped app
**verifies then previews (diff) then applies** the bundle, recording provenance
and an audit event. A verdict-changing downgrade needs explicit confirmation (or
is written `needs_review`). **The running app never makes an outbound request.**
*(007 US3)*

### Area G — Compliance: Default-Credential Tool (P1)

**G1 — Standalone, exhaustive-by-default, device-safe check.** Runs on demand or
on its own schedule against an explicit target + port/service, trying a
**selected dictionary**. It tries every credential in the dictionary once
(ceiling defaults to dictionary size; operator may lower it), **≥5s between
attempts (non-negotiable)**, **stops on the first match**. Exhausted-no-match →
compliant; capped-short-no-match → inconclusive; match → non-compliant ("default
credentials in use"). Never part of a discovery run. HTTP/HTTPS authenticate via
a form flow (status + body), tolerating self-signed TLS. Runs show `running`
immediately (background worker + polling); the result window is a per-attempt
table highlighting the matching row by **username only**. **The attempted/matched
password is never shown, stored, or logged.** *(001 US6 → 002 US5, 008 US1–US7)*

**Acceptance (representative):**
1. A dictionary of N creds with the k-th valid → exactly k attempts, ≥5s apart,
   stops at k; none valid → all N tried → compliant.
2. HTTP/HTTPS issues a POST and distinguishes accepted vs rejected (status+body);
   self-signed certs tolerated.
3. A started run appears as `running` within one poll interval and transitions to
   completed without a manual refresh.
4. The result table shows username, response, outcome, matching row highlighted;
   no password text anywhere; the check is audited.

### Area H — Results → Host Pivot (P1)

**H1 — Select hosts and pivot.** On a completed run's results, tick host rows (or
**Select invalid-version hosts** — non-compliant only, unioned with any manual
selection) and either **Check credentials on selected** (opens the credential
tool pre-filled with those addresses; operator picks port/service/dictionary) or
**Scan selected with profile…** (opens the Scan Configuration window pre-filled
with those hosts and the chosen profile). De-duplicated; duplicate concurrent
runs prevented; everything audited; guardrails unchanged. *(009 US2–US4)*

### Area I — Database Upgrades (P1, operational)

**I1 — Safe in-place upgrade.** One documented offline step brings an existing
database to the current schema, preserving all data; it is idempotent, makes a
**recovery copy** before any change (and aborts if it can't), and stamps the
schema version. Fresh install produces an already-current, stamped database.
Startup **fails fast** with one clear message on a behind-schema database and
**refuses** an ahead-of-code database; the scheduler heartbeat never floods the
log on a mismatch. *(004 US1–US3)*

### Area J — Presentation: Tactical-HUD UI (P1 visual)

**J1 — One coherent tactical-HUD language** across all twelve screens (login,
home, profiles, profile editor, history, run detail, schedules, credential tool,
scan config, configuration, tool run detail, results): amber-on-near-black, Volja
wordmark, bracketed/notched panels, mono/tabular data fonts, ambient HUD
decoration. **Compliance status stays instantly scannable**; every state is
conveyed by **text + color, never color alone**; WCAG 2.1 AA contrast;
decoration is non-interactive, hidden from assistive tech, capped in intensity,
and respects reduced-motion. **Presentation-only — no behavior change.** Fully
air-gapped (all assets local). *(002 US6 → 010 US1–US3)*

---

## 5. Edge Cases (consolidated)

- Empty/unreachable scope → "no responding hosts", not an error; oversized scope
  stays responsive and shows progress. *(001)*
- `nmap` missing / insufficient privilege → clear actionable error; run recorded
  failed, not silently empty. *(001)*
- Disallowed scan parameter / raw flag → rejected at save; never executed. *(001, 002)*
- Legacy profile with forced extraction or a host-link value → loads and runs;
  host-link value ignored, not shown. *(002)*
- NSE script removed from allow-list while referenced → off-list script never
  runs; the condition is surfaced/flagged. *(002)*
- Last Administrator / lowering the 20-char floor → prevented. *(002)*
- Exactly 10 ports → small scan; host-up-all-filtered (small) shows each port's
  state; host-up-no-open (large) shows "Всі порти closed або filtered". *(003)*
- Non-compliant product with no "valid" floor → orange, shows the note; nothing
  invented. *(003, 007)*
- Target-less profile launched without a target → blocked with a prompt, no
  empty-target scan; invalid launch target → rejected like a profile target. *(003, 009)*
- Deleting a profile with schedules → its schedules are removed/disabled (no
  orphan firing). *(003)*
- "Once" time in the past (incl. elapsing before save) → rejected inline;
  "every 1 month" from the 31st → valid day in shorter months, no stall. *(005)*
- Legacy DB with no version stamp → recognized, reconciled, brought current
  without failing on existing structures; interrupted upgrade → recover from the
  copy; backup target unavailable → abort before mutating. *(004)*
- Unparseable/mixed-scheme version or threshold → unknown, never guessed;
  ingestion source drift / apparent downgrade → fail safe / surface for review,
  never silently change a threshold; empty dictionary → everything unknown. *(007)*
- Credential dictionary deleted mid-run → run uses the snapshot taken at start;
  HTTP target unreachable → recorded as an error outcome, counts toward pacing,
  run completes; background worker crash → run marked `failed`, never stuck
  `running`. *(008)*
- Pivot with nothing selected → pivot actions disabled; run not version-evaluated
  → **Select invalid-version hosts** disabled with an explanation; large selection
  → one valid de-duplicated target. *(009)*
- Missing Volja glyph → legible fallback (display font limited to wordmark/
  headings); narrow viewport → panels stack, decoration stays behind content, no
  horizontal page scroll; air-gapped load → every font/style/decoration renders
  with no external fetch. *(010)*

---

## 6. Requirements (final state)

Requirements are grouped by theme and reflect the **shipped** behavior. Where a
later feature superseded an earlier FR, the final rule is stated and the origin
noted.

### Authentication & Access Control

- **R-A1**: No page, data, or action is reachable without a successful local
  sign-in. *(001 FR-001)*
- **R-A2**: Enforce a password policy of **≥20 characters** at creation and every
  change, rejecting non-compliant passwords with a clear reason; the floor can
  never be lowered below 20 at runtime. *(001 FR-002, 002 FR-032)*
- **R-A3**: Store credentials only locally and only as a strong one-way hash
  (Argon2id); never plaintext/recoverable. *(001 FR-003, Constitution II)*
- **R-A4**: Throttle/lock sign-in after a configurable number of consecutive
  failures. *(001 FR-004)*
- **R-A5**: Maintain sessions with a configurable idle timeout and explicit
  sign-out. *(001 FR-005)*
- **R-A6**: Support exactly two roles — **Administrator** and **Operator** (no
  viewer). User management, account/session security settings, and NSE allow-list
  management are **Administrator-only, enforced server-side**. Operators do all
  discovery work, run the tools, manage the version dictionary, and change their
  own password. *(002 FR-027/028/031, 006 FR-014/015, Constitution VII)*
- **R-A7**: First account on a fresh install is Administrator; later accounts
  default to Operator. Never allow zero active Administrators. Deactivation/role
  change/password reset invalidates the user's session at next action. *(002
  FR-030/033/034)*

### Discovery Profiles & Command Composition

- **R-B1**: Create, view, **edit (via an Edit button)**, duplicate, and delete
  profiles; edits update in place with optimistic-concurrency conflict detection
  and field-level validation. *(001 FR-007, 002 FR-002/003)*
- **R-B2**: A profile captures target scope (hosts/ranges/subnets, **optional**),
  port/service selection, timing template (**default `T3`, changeable T0–T5**),
  independent extract-open-ports / extract-service-version toggles, and selected
  NSE scripts. **No host-management link field.** *(001 FR-008/009/010/012, 002
  FR-001/004/005/006, 003 FR-003a)*
- **R-B3**: Validate parameters against an allow-list at save; reject malformed
  targets/disallowed options with specific messages. The command is composed
  **only from vetted allow-listed options**; no raw/free-form flag string is ever
  accepted (command-injection guard). *(001 FR-011, 002 FR-009, Constitution
  Security)*
- **R-B4**: Selecting service-version extraction enables service detection; when
  deselected, no service probing occurs and results omit versions without error.
  *(002 FR-007)*
- **R-B5**: Show the exact effective command before running, including with no
  target (clearly-marked placeholder). The ports field shows its full contents.
  *(002 FR-008, 006 FR-008/009/010)*
- **R-B6**: Persist profiles across restarts. *(001 FR-014)*

### NSE Scripts

- **R-N1**: A profile selects zero or more NSE scripts from a checklist/list
  control populated by the current allow-list, applying exactly those scripts;
  output is captured per host in results and history. *(002 FR-010/011, 003
  FR-016/017)*
- **R-N2**: The allow-list is Administrator-maintained from Configuration (add/
  edit/remove, validated, audited). A profile can never run an off-list script;
  stale selections are prevented/flagged. *(002 FR-012/013/014/018)*
- **R-N3**: Adding a script outside Nmap's "safe" categories warns but is
  permitted (and audited); the default allow-list ships safe-category scripts
  only (e.g. `mikrotik-routeros-version`). *(002 FR-015/016)*
- **R-N4**: NSE scripts execute only from the locally installed `nmap` — no
  download or network activity; a script needing an unscanned port SHOULD warn.
  *(002 FR-017/019, Constitution I)*

### Discovery Execution & Results

- **R-C1**: Orchestrate `nmap` per the profile's vetted parameters; start runs on
  demand with progress/completion; allow cancel (recorded cancelled, partial
  results kept). *(001 FR-015/016/017)*
- **R-C2**: Present results per responding host with the selected telemetry and
  per-host NSE output; empty vs failed runs are distinct and clear. *(001
  FR-018/020, 002 FR-011)*
- **R-C3**: Port column by scan size — ≤10 ports (counted from results) shows
  each port's state; >10 shows only open; a filtered/closed port is never shown
  as open; a large-scan host with no open ports shows "Всі порти closed або
  filtered". Service version is derived from an open port. *(003 FR-009/009a/009b/
  010/011)*
- **R-C4**: Limit concurrent discovery activity and prevent duplicate concurrent
  runs of the same profile regardless of trigger. *(001 FR-021/043)*
- **R-C5**: Run now opens a **Scan Configuration window** (not a browser prompt)
  pre-filled from the profile, editing only target/ports/timing/extracted fields
  for that run with a live command preview and Start Scan; target-less blocks
  Start Scan until valid; nothing writes back to the profile; same validation/
  allow-list as the editor. *(009 FR-013–FR-018)*

### History, Caching & Dynamic UI

- **R-H1**: Persist every run (timestamp, profile, parameters, status, full
  results); list newest-first; open any run to its captured results. *(001
  FR-022/023)*
- **R-H2**: Serve recent results from a configurable freshness-window cache
  (labeled with original time); allow "force fresh". Apply a configurable
  retention policy. Deleting a profile keeps its historical runs. *(001
  FR-024/025/026/027)*
- **R-H3**: After a user-initiated mutation, the affected view updates without a
  manual reload; a failed mutation leaves the view consistent and signals the
  error. *(003 FR-006/007/008)*

### Home Dashboard

- **R-D1**: Home is titled "Головна" (not "Панель відповідності"); never empty
  when profiles exist; two-column layout (narrow → stacked, no horizontal page
  scroll). The heading/subtitle filler is removed. *(003 FR-001/002/004, 006
  FR-001/002)*
- **R-D2**: Left column: 5 most-recently-updated profiles (each with Run now) and
  the 5 soonest-next-run scheduled tasks (click → Schedules). Right column: the
  20 most-recent scans across all profiles; compliance posture where evaluated,
  "not applicable" otherwise; the retained compliance signal is the non-compliant
  count. Each section has a non-error empty state. *(003 FR-002/003/005/005a, 006
  FR-003/004/005/006)*

### Scheduling

- **R-E1**: One shared scheduling engine serves profile-scan schedules and tool
  tasks (no second scheduler). *(002 FR-021, 003 FR-022, Constitution VI)*
- **R-E2**: A schedule is an independent task referencing a profile (or the tool),
  carrying **its own target** (default from the profile) and optional label; a
  profile may have multiple; editing a schedule never edits the profile; a later
  change to the profile's target never alters an existing schedule. A schedule's
  target passes the same validation; a schedule can be created from a past run
  (prefilling profile/target/parameters). *(003 FR-020/021/021a/021b/023, 004
  FR-013)*
- **R-E3**: Recurrence is **once** or **interval** (both for scans and the
  credential tool). Once (listed first): day → hour(0–23) → minute; runs exactly
  once then marked completed; past time rejected inline. Interval: positive whole
  number + unit (minute/hour/day/week/month, Ukrainian); recurs every N units;
  month roll-over graceful; non-positive/non-integer rejected inline. Legacy
  daily/weekly removed from the UI (engine still accepts them). *(005
  FR-001–FR-012, 008 FR-101/103)*
- **R-E4**: Schedules are editable in place (recurrence/target/label/enabled),
  validated like creation, recomputing next-run, audited, no duplicate created.
  Next-run is displayed; overlap and catch-up policies apply; scheduled runs are
  recorded in history and audit identically to manual runs. *(001 FR-028–FR-032,
  005 FR-016/017)*
- **R-E5 (credential task table)**: shows an **Enabled** column and a **Next check
  time** column (replacing the raw period column); edit round-trips the correct
  kind without once→interval conversion. *(008 FR-101/102)*

### Compliance — Version Validity (offline)

- **R-F1**: Determine validity by comparing the detected version to the product's
  **minimal recorded (current) threshold**: below → non-compliant; at/above →
  compliant; no threshold → unknown. Multiple recorded versions → the minimal is
  the threshold. *(007 FR-001–FR-005; supersedes 001 FR-034/035 enumerated model)*
- **R-F2**: Order versions SemVer-style (numeric left-to-right; missing trailing
  = 0; pre-release/suffix below the same base); unorderable/mixed-scheme →
  unknown, never guessed. *(007 FR-006)*
- **R-F3**: Non-compliant rows highlight orange and surface the expected/target
  version; compliant/unknown rows are not highlighted. *(003 FR-012/013/014, 007
  FR-007)*
- **R-F4**: **Zero external/network lookups** for version evaluation — resolve
  only against local reference data. *(001 FR-034/SC-009, 007 FR-008, Constitution
  I)*
- **R-F5**: The version dictionary is viewable and editable in-app by Operators
  and Administrators (Configuration → Бібліотека); every edit is audited. Legacy
  enumerated data is migrated (lowest `valid` → threshold; invalid-only surfaced
  for review). *(003 FR-015/015a/015b, 006 FR-012/013/013a, 007 FR-009/010/011/012/
  013)*
- **R-F6 (immutable history)**: At scan time, the verdict and checked version are
  stored as fixed values and never recalculated when thresholds/settings change;
  only later scans reflect a new threshold. *(007 FR-012a)*

### Compliance — Automated Version Ingestion (offline-safe)

- **R-G1**: An Administrator defines tracked entries (vendor, official source
  URL, models) in the library. *(007 FR-014)*
- **R-G2**: A **standalone staging fetcher** (separate internet-connected machine,
  never imported by the app) fetches current versions per vendor/models and emits
  a defined, documented **bundle** carrying vendor/model/version/source/timestamp
  and an integrity/authenticity check. *(007 FR-015/016)*
- **R-G3**: On import the deployment **verifies integrity first** (failure →
  rejected, no change), then lists candidates for **review** and, on **apply**,
  creates/updates thresholds; provenance and the import are audited. A
  verdict-changing downgrade is applied only after explicit review (else written
  `needs_review`). *(007 FR-016a/017/018/020)*
- **R-G4**: **The running compliance app makes no outbound internet request;** all
  vendor fetching happens only in the staging fetcher. Tracked entries, thresholds,
  and bundles are local, offline-maintainable reference data. *(007 FR-019/021,
  Constitution I)*

### Compliance — Default-Credential Tool (device-safe)

- **R-K1 (standalone)**: The check is a separate tool run on demand or on its own
  schedule against an explicit target + port/service with a **selected
  dictionary**; it never runs as part of a discovery profile's run. Launching from
  a result row / pivot prefills the target(s). *(002 FR-020, 008 FR-104, 009
  FR-006/008)*
- **R-K2 (attempt ceiling, configurable)**: The per-target attempt ceiling is
  **operator-configurable and defaults to the selected dictionary's size** (try
  every credential once by default); the check must not exceed the effective
  ceiling. *(008 FR-108, Constitution III)*
- **R-K3 (cooldown, non-negotiable)**: Consecutive attempts against a target are
  separated by **≥5 seconds**, enforced centrally; this cannot be shortened or
  waived by any configuration or code path. *(001 FR-037, 002 FR-022, 008 FR-109,
  Constitution III)*
- **R-K4 (stop-on-match & verdicts)**: Stop at the first accepted credential. A
  body-signature match → non-compliant ("default credentials in use"); a fully
  exhausted dictionary with no match → **compliant**; a ceiling set below the
  dictionary size preventing a conclusive result → **inconclusive**. *(008
  FR-110/111, Constitution III)*
- **R-K5 (HTTP/HTTPS form probe)**: Authenticate via a form flow — GET to
  fingerprint, POST the credential to the configured login path, judge by
  **status code AND body content**; never conclude from a bare GET of `/`. HTTPS
  reuses the mechanism over TLS and tolerates self-signed certificates. A
  dictionary may carry HTTP form settings (login path, method, field names,
  success/failure criteria, optional fingerprint/CSRF). *(008 FR-105/106/107)*
- **R-K6 (live status & result window)**: A started run is committed as `running`
  and executed on a background worker; the UI polls to completion (a crashed
  worker → `failed`, never stuck). The result view is a per-attempt table
  (target, username, response, outcome) styled like a scan result, highlighting
  the matching row. *(008 FR-112/113/117)*
- **R-K7 (secret non-persistence)**: The matched credential is identified by
  **username and dictionary entry only**; the attempted/matched **password is
  never displayed, persisted, or logged** (result rows, run record, audit log).
  *(001 FR-039, 008 FR-114, Constitution II/IV)*

### Results → Host Pivot

- **R-P1**: The results view offers per-row host selection, select-all/clear, a
  selected-count, and a **Select invalid-version hosts** action (non-compliant
  only; disabled with an explanation when the run wasn't version-evaluated;
  unions with an existing manual selection). *(009 FR-001–FR-005)*
- **R-P2**: Pivot the selection into a credential check (navigates to the tool
  pre-filled with the addresses; operator still chooses port/service/dictionary;
  guardrails unchanged; audited) or into a new scan via the Scan Configuration
  window (pre-filled with those hosts + the chosen profile; targets exactly the
  shown de-duplicated list; profile unchanged). Duplicate concurrent runs
  prevented; both roles may pivot. *(009 FR-006–FR-012/019/020)*

### Database Upgrades & Reliability

- **R-U1**: One documented offline step brings an existing database to the schema
  the code expects, preserving all data, idempotent, with no new runtime
  dependency. *(004 FR-001/002/003/009)*
- **R-U2**: Each database records its schema version; fresh install is already
  current and stamped; legacy un-stamped databases are recognized and reconciled
  without failing on existing structures. *(004 FR-004/005/006)*
- **R-U3**: Before any schema change, create a **recovery copy**; if it can't be
  created, stop before mutating and report why. *(004 FR-007/008)*
- **R-U4**: On startup, a behind-schema database → **fail fast** with one clear
  message (no silent serving, no heartbeat traceback flood); an ahead-of-code
  database → refuse and report. After upgrade, the full scheduling feature works.
  *(004 FR-010/011/012/013)*

### Presentation, Localization & Accessibility

- **R-J1**: A single coherent **tactical-HUD** visual language (amber-on-near-
  black, Volja wordmark, bracketed/notched panels, mono/tabular data fonts,
  ambient HUD decoration) across all twelve screens, driven by shared tokens and
  components; no screen left in the old flat theme. *(002 FR-035/036, 010
  FR-001–FR-010)*
- **R-J2**: UI text is **Ukrainian** via a single-locale catalog; technical
  identifiers stay English; every config control has a `?` help annotation. *(002
  FR-037/038, 005 FR-011, 006 FR-017, 007 FR-022, Constitution VI)*
- **R-J3**: Ambient decoration is purely cosmetic (non-interactive, hidden from
  assistive tech, capped intensity behind data, reduced-motion aware, generated
  without external assets). *(010 FR-011–FR-015)*
- **R-J4**: Meet **WCAG 2.1 AA** contrast; every compliance/run/status state is
  conveyed by **text + color, never color alone**; non-compliant/failed states are
  emphasized and instantly scannable; keyboard focus is clearly visible. *(010
  FR-016–FR-019/017a)*
- **R-J5**: No external runtime fetch of fonts/styles/scripts/images — all assets
  local; the Volja font is served locally with a defined fallback. *(010
  FR-020/021, Constitution I)*
- **R-J6 (non-regression)**: The redesign changes presentation only — no change to
  behavior, data, auth policy, scan orchestration, scheduling, caching, compliance
  evaluation, or the credential-check safety limits; all existing affordances
  remain functional. *(010 FR-022–FR-026)*

### Auditability (cross-cutting)

- **R-X1**: Record to an append-only audit log: sign-in success/failure, lockouts,
  profile changes, run executions, compliance checks, schedule changes, user-
  management/role actions, security-settings changes, NSE allow-list changes,
  reference-version edits, and bundle imports. Records carry enough detail to
  verify the device-safety invariants (attempt counts and timings) and **contain
  no secrets**. *(001 FR-006, 002 FR-014/024/029/031, 003 FR-015b, 007 FR-018,
  Constitution IV)*

### Offline & Dependency Constraints (cross-cutting)

- **R-O1**: Zero internet access at install and runtime; all dependencies vendored
  (local wheelhouse / committed static assets); all reference datasets local and
  offline-updatable; no new runtime dependency introduced by any later feature.
  *(001 FR-040, 003 FR-019, 004 FR-009, 005 FR-015, Constitution I)*

---

## 7. Key Entities

- **Operator Account & Role** — username, Argon2id password material, role
  (Administrator/Operator), active/deactivated state, lockout/throttle state,
  audit trail.
- **Configuration / Security Settings** — password minimum length (≥20 floor),
  lockout threshold/duration, session idle timeout; the hub for user management,
  NSE allow-list, and the version dictionary.
- **Asset Discovery Profile** — name, description, optional target scope,
  port/service selection, timing template (`T3` default), independent extraction
  toggles, selected NSE scripts, version-compliance toggle, caching/freshness
  settings. (No host-management link.)
- **Discovery Run / Host Result** — timestamp, profile + exact parameters used
  (incl. one-off launch target), trigger, status (running/completed/cancelled/
  failed), cache flag, per-host open ports + states, detected service/version,
  per-host NSE output, compliance findings.
- **Compliance Finding** — control type (version validity / default credentials),
  result (compliant / non-compliant / unknown / inconclusive), the checked value
  and threshold frozen at scan time, supporting detail, timestamp.
- **Schedule** — references a profile or the tool; recurrence (once | interval
  N×unit), own target, optional label, enabled state, next-run, overlap/catch-up
  policy.
- **Reference Version Threshold** — product/vendor/model identity, one or more
  current versions (minimal = active threshold), note/remediation, provenance
  (manual vs ingested, source, last-updated). *(replaces the enumerated row)*
- **Tracked Ingestion Entry** — vendor, official source URL, models, last-import
  status/version.
- **Version Update Bundle** — per-model vendor/model/version/source/timestamp (+
  per-model failure) with an integrity/authenticity check; produced by the
  staging fetcher, verified/reviewed/applied on import.
- **Credential Dictionary (`DefaultCredentialEntry`)** — per-service named list of
  `{username, secret}` pairs, success keywords/signatures, HTTP form-probe
  settings; selectable per run/task.
- **Tool Task / Check Run / Result** — the standalone credential check: task
  (recurrence + chosen dictionary), run (live `running` status), result
  (per-attempt list: username, response summary, matched flag — password-free).
- **Schema Version Record / Migration / Recovery Copy** — the DB-upgrade entities.
- **Audit Log Entry** — a security-relevant event, secret-free.

---

## 8. Success Criteria (measurable)

- **SC-01**: 100% of pages/data/actions are inaccessible without sign-in; 100% of
  sub-20-char passwords rejected at creation and change.
- **SC-02**: A profile (any extraction combination, any T0–T5, optional target)
  can be created/edited in place; the command preview matches the selections
  exactly and never carries a raw flag.
- **SC-03**: Small scans show each port's state; large scans show only open ports;
  0% of filtered/closed ports are shown as open.
- **SC-04**: 100% of non-compliant version rows are orange and show the target
  version; 0% of compliant/unknown rows are highlighted.
- **SC-05**: Version-validity evaluation completes with **zero** external/network
  lookups, verifiable in the air-gapped environment.
- **SC-06**: Historical verdicts are immutable — 100% of stored verdicts and
  checked versions are unchanged after a threshold/setting change; only later
  scans reflect the new threshold.
- **SC-07**: The credential check never shortens the ≥5s cooldown and never
  exceeds the effective ceiling (default = dictionary size), verifiable from the
  audit log across 100% of checks; a dictionary of N with the k-th valid → exactly
  k attempts, stop at k; none valid → all N tried → compliant.
- **SC-08**: No attempted/matched password appears anywhere (UI, stored records,
  audit log) across 100% of checks.
- **SC-09**: HTTP/HTTPS checks issue a POST and correctly distinguish accepted vs
  rejected (status + body), tolerating self-signed TLS.
- **SC-10**: A started credential run appears as `running` within one poll
  interval and reaches completed/failed without a manual refresh; no run is ever
  stuck `running`.
- **SC-11**: The Home page is never empty when profiles exist and surfaces 100% of
  recent scans regardless of compliance configuration; a run is launchable from
  Home in one action.
- **SC-12**: After any user-initiated mutation, the affected view reflects the
  change with no manual reload in 100% of successful operations.
- **SC-13**: A discovery profile can be scheduled (once or interval) without
  editing the profile, with the schedule's own target; scheduled runs are recorded
  like manual runs; 0 duplicate concurrent runs.
- **SC-14**: A fresh-install database and an upgraded database have identical
  structure and schema version; the upgrade is idempotent, offline, makes a
  recovery copy, and a behind-schema startup produces exactly one clear message
  with no heartbeat error flood.
- **SC-15**: An operator can pivot selected hosts into a scan (≤3 actions, no
  retyping addresses) or a credential check; **Select invalid-version hosts**
  selects 100% of non-compliant and 0% of compliant/unknown; every pivot is
  audited and honors the guardrails.
- **SC-16**: All twelve screens render in the tactical-HUD language (0 left flat);
  every status is distinguishable in grayscale (text + color); AA contrast met; no
  decoration is focusable or announced; reduced-motion disables animation; every
  screen renders fully offline with no horizontal page scroll at supported widths.
- **SC-17**: The system supports ≥5,000 hosts and a /22 run, rendering results and
  history without perceptible degradation (history list < 3s).
- **SC-18**: The full automated test suite (including the CI invariant suite: auth
  gate, ≥20-char policy, credential guardrails, offline version check, no duplicate
  concurrent runs, optimistic-concurrency conflict detection, RBAC, NSE allow-list
  enforcement) passes.

---

## 9. Assumptions

- **Authorized use** against the organization's own internal infrastructure; the
  operators are trusted administrators.
- **Air-gapped deployment** — no internet at install or runtime; all reference
  data provisioned/updated locally. The only component permitted an outbound
  request is the out-of-runtime staging fetcher, run on a different machine.
- **Designated tool** — `nmap` installed on the host with privileges sufficient
  for the configured scan types; the app orchestrates it rather than replacing it.
- **Single-tenant local install** — one host, a few operators, a single local
  SQLite database under `data/`, operated with the app stopped during upgrades.
- **Two roles**, no viewer; profiles/reference data are shared across operators.
- **Host-management link** deferred to a future standalone function.
- **Single dark (tactical-HUD) theme**, no toggle; single Ukrainian locale, no
  runtime language switcher; technical identifiers kept in English.
- **Version comparison** uses the SemVer-style ordering fixed in R-F2; "official
  source" authenticity is an administrator responsibility, not an automated trust
  decision.
- **One scheduling engine** serves both schedule kinds; heartbeat granularity
  (~30s) means "runs at T" = "within one heartbeat cycle of T".

---

## 10. Out of Scope (v1)

- Automated remediation of findings (Milmap detects and reports; it never changes
  device configuration).
- External IdP/SSO, multi-site federation, internet-based data feeds at runtime.
- A read-only viewer role or per-permission RBAC beyond Administrator/Operator.
- Raw/free-form nmap flag entry; fetching NSE scripts from outside the local
  install.
- Weakening or waiving the ≥5-second credential cooldown or central enforcement.
- The returning host-management-link standalone function.
- Automatic-on-startup database migration (the upgrade stays an explicit,
  documented, auditable step).
- Non-HTTP credential-probe rewrites beyond what the shared attempt-loop changes
  require; credential brute-forcing beyond operator-provided dictionaries.

---

## 11. Governing Constitution

This specification is governed by the project Constitution **v2.0.0**
(`.specify/memory/constitution.md`): I. Offline-First / Air-Gapped; II. Security
by Default; **III. Device-Safety Invariants (NON-NEGOTIABLE)** — ≥5-second
cooldown and central enforcement/stop-on-match are un-waivable, the attempt
ceiling is operator-configurable (default = dictionary size); IV. Auditability;
V. Testable & Independently Deliverable; VI. Simplicity (YAGNI, one scheduler,
single-locale); VII. Least-Privilege Roles.

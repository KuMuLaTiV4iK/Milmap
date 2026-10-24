# Phase 0 Research: Credential-Check Tool Fixes

All open questions from the spec's Clarifications were resolved with the project
owner before planning; this document records the resulting technical decisions
and the reasoning, plus the small amount of codebase research that shaped them.

## D1 — "once" selection stored/shown as interval (3.1.1)

**Decision**: The backend (`compute_next_run_at` / `validate_recurrence`) already
handles `once` correctly; the defect is front-end only. Rebuild the task form's
recurrence controls to mirror `schedules.html` exactly — a kind `<select>`
(once/interval), a once group (date/hour/minute → absolute naive-UTC ISO via
`Date.toISOString()`), and an interval group (every + unit) — and make
`buildTaskRecurrence`/`editTask` round-trip both shapes.

**Rationale**: Verified in code: `compute_next_run_at({type:'once',run_at})`
returns the fixed instant; `validate_recurrence` rejects a past `once`. The scan
scheduler's JS is the known-good reference. Reusing its exact pattern removes the
divergence that produced once→interval.

**Alternatives considered**: Patching the current ad-hoc interval-only field —
rejected; it can't represent `once` and would keep drifting from the scan UI.

## D2 — Task-table columns: Enabled + Next check time (3.1.2, 3.1.3)

**Decision**: Render an **Enabled** column from `task.enabled` and replace the raw
recurrence/period column with a **Next check time** column from `task.next_run_at`
(localized like the scan table). Keep a human-readable recurrence as secondary
text if space allows, but the dedicated columns are the requirement.

**Rationale**: The API already serializes `enabled` and `next_run_at`; this is a
template/JS change only.

## D3 — Dictionary selection per run/task (3.2)

**Decision**: Treat each `DefaultCredentialEntry` as a selectable "dictionary".
Add a `dictionary_id` to run-now requests and to `ToolTask`. The run/task forms
load dictionaries for the chosen service (`GET /credentials?service=`) and show a
selector; the check scopes candidates to that one dictionary. Single-select.

**Rationale**: Matches the owner's model ("choose dict"), bounds the new
exhaustive-attempt semantics, and keeps per-service scoping. The dictionary is
already per-service, so the selector is filtered by the form's service field.

**Alternatives considered**: Multi-select / "all dictionaries for service" —
rejected as the default; it makes the attempt ceiling ambiguous and the owner
asked to choose one. (Could be added later without breaking the single-select
contract.)

## D4 — Form-aware HTTP/HTTPS probe (3.3.1, 3.3.2)

**Decision**: Replace the Basic-auth GET with a four-step flow, per the owner:
1. **Fingerprint** — GET the base URL; capture status, body signature, and any
   CSRF/anti-forgery token the dictionary's settings name.
2. **Select settings** — use the chosen dictionary's HTTP probe settings (login
   path, method=POST, username/password field names, extra static fields,
   optional token field, success/failure criteria). Fingerprint signatures may
   gate whether these settings apply.
3. **Submit** — POST the credential (form-encoded by default) to the login path.
4. **Validate** — success = configured **status-code set AND/OR body-keyword**
   rule; a 401/403 (or configured failure signature) is a rejection, which also
   distinguishes "accepted" from "the login page reloaded".

HTTPS reuses the same code over `scheme="https"` with **`verify=False`** so
self-signed certificates on internal devices don't fail the attempt.

**Rationale**: The owner's server shows `POST /login → 401/200`; the current
probe only does `GET / → 200` and keyword-matches the login page, which is why it
reports false results. httpx supports `verify=False`, form `data=`, cookies, and
header capture — no new dependency.

**Alternatives considered**: Basic-auth-by-status (option offered) — rejected by
the owner; doesn't fit form login. Fixed convention with no per-dict config —
rejected; devices vary. CSRF handling is included but marked deferrable if a
target doesn't issue a token.

**Security note**: `verify=False` is scoped to this internal-asset probe on an
air-gapped network (Principle I context), never to general outbound calls.

## D5 — Configurable attempt ceiling + stop-on-match (3.3, 3.6)

**Decision**: Parameterize the central guard in `credential_check.py` with a
per-target **ceiling** defaulting to the selected dictionary's size; stop
immediately on the first accepted credential; keep the ≥5s cooldown between
consecutive attempts. Exhausting the dictionary with no match ⇒ `compliant`; a
configured ceiling below dictionary size that is hit without a match ⇒
`inconclusive`.

**Rationale**: Requires and is covered by the **constitution v2.0.0 amendment**
(Principle III) the owner authorized. Central enforcement is preserved (the
ceiling is applied in the one orchestrator, not per-probe). The cooldown — the
real lockout-timing safeguard — stays non-negotiable.

**Alternatives considered**: Unbounded attempts (no ceiling) — rejected; removes
all lockout protection. Fixed higher cap — rejected; still truncates larger
dictionaries.

## D6 — Background execution + polling (3.4)

**Decision**: Add `tools/credential_tool/runner.py` mirroring
`discovery/runner.py`: a module-level lock + registry, commit the `ToolCheckRun`
as `running`, then run the probing loop on a daemon thread; finish by setting
`completed`/`failed` in a fresh session. The run-now endpoint returns the
`run_id` immediately; the history and result views poll (~3s, as
`run_detail.html` already does) until terminal.

**Rationale**: `ToolCheckRun.status` already exists (RUNNING/COMPLETED/FAILED).
The discovery runner is the proven in-repo pattern; cred runs need a parallel but
separate orchestrator because their lifecycle (internal cooldown loop, no
subprocess, no profile concurrency key) differs — justified in Complexity
Tracking.

**Alternatives considered**: Commit-running-then-stay-synchronous (offered) —
rejected by the owner (HTTP response still blocks). Reusing the discovery runner
directly — rejected (tight nmap/DiscoveryRun coupling).

**Failure handling**: A worker exception marks the run `failed` with
`error_detail` and clears the registry, so no run is stuck `running` (FR-117),
matching `_finish_failed` in the discovery runner.

## D7 — Result window: per-attempt table, username-only highlight (3.5)

**Decision**: Persist a per-attempt list on `ToolCheckResult.detail`
(`attempts: [{username, status, excerpt, matched}]`) — **username only, never the
secret**. Add a `tool_run_detail.html` page styled like `run_detail.html` with a
table of attempts per target, highlighting the matched row by username and
dictionary entry. While a run is `running`, the page polls and shows partial
progress.

**Rationale**: Usernames are not secrets (Principle II/ FR-039 govern the
password only). Storing per-attempt metadata enables the scan-style table and
survives reloads. The password is never written or rendered, satisfying FR-114.

**Alternatives considered**: Show/persist the matched password (offered) —
rejected by the owner (username-only). In-memory-only display — rejected; loses
the table across reloads and complicates polling.

## D8 — Dictionary HTTP settings storage

**Decision**: Store HTTP probe settings in a JSON column on
`DefaultCredentialEntry` (e.g. `probe_config`) with sensible defaults
(`login_path="/login"`, `method="POST"`, `username_field="username"`,
`password_field="password"`, `success={status:[200,302],keywords:[...]}`,
`failure={status:[401,403]}`, optional `fingerprint`/`csrf`). Defaults apply when
the column is empty, so existing seeded dictionaries keep working.

**Rationale**: JSON column matches how the codebase already stores flexible
per-row config (recurrence, success_keywords, scan_params). No schema migration
machinery beyond adding a nullable column (SQLite + create_all for fresh DBs;
existing DBs get the column via the same additive approach the project already
uses — see data-model.md migration note).

## D9 — Layout refinements (3.7, 3.8)

**Decision**: Run-now card: target input on row 1; port + service + dictionary +
start button in a flex row on row 2. Dictionary form: make the description/vendor
field full width. Pure template/CSS changes.

**Rationale**: Cosmetic; no behavioral impact; uses existing CSS utility classes.

## Codebase facts confirmed during research

- `scheduling/engine.py` already dispatches `ToolTask`s via `_tick_tool_tasks`
  and supports once/interval through shared helpers — no scheduler change needed.
- `discovery/runner.py` provides the exact background pattern to mirror (lock,
  registry set, daemon thread, fresh-session finishers, `_finish_failed`).
- `compliance/credential_check.py` centralizes the guard and already accepts an
  injectable `sleep_fn` (keeps cooldown tests fast) — the ceiling parameter slots
  in here.
- `DefaultCredentialEntry` already stores `credentials` and `success_keywords` as
  JSON; adding `probe_config` is consistent.
- `ToolCheckRun.status` and archival already exist; only the execution path needs
  to become asynchronous.

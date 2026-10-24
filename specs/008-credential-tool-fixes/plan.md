# Implementation Plan: Credential-Check Tool Fixes

**Branch**: `008-credential-tool-fixes` | **Date**: 2026-10-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/008-credential-tool-fixes/spec.md`

## Summary

Fix and harden the standalone credential-check tool: give its scheduler full
once/interval parity with scan schedules (and honest Enabled / Next-check-time
columns), let operators pick a specific credential dictionary per run/task,
replace the broken Basic-auth-GET HTTP/HTTPS probe with a form-aware
fingerprint→POST→validate flow that tolerates self-signed TLS, change the
attempt loop to exhaust the chosen dictionary under an operator-configurable
per-target ceiling (default = dictionary size) while keeping the non-negotiable
≥5s cooldown and adding explicit stop-on-match, run checks on a background thread
so they appear as `running` immediately and are polled to completion, and replace
the `alert()` result with a scan-style per-attempt result table that highlights
the matching attempt by **username only** (no password ever shown or stored).
Two layout refinements round it out (run-form two-row layout, wide dictionary
description field).

Technical approach: extend the existing `tools/credential_tool/` module and its
`ToolTask`/`ToolCheckRun`/`ToolCheckResult` models rather than introducing new
subsystems; reuse the shared scheduling engine and recurrence helpers; mirror
`discovery/runner.py`'s background-thread + registry pattern for cred runs;
parameterize the central guard in `compliance/credential_check.py` with a ceiling
and per-attempt record callback; add HTTP form-probe settings to
`DefaultCredentialEntry`.

## Technical Context

**Language/Version**: Python 3.12 (runtime); project venv is 3.12 per logs.

**Primary Dependencies**: FastAPI + Starlette, SQLAlchemy 2.x ORM, Jinja2
templates (server-rendered, htmx + vanilla JS), httpx (HTTP/HTTPS probe),
APScheduler (heartbeat only), Argon2 (auth; unaffected). No new dependency.

**Storage**: SQLite (`data/app.sqlite3`) via SQLAlchemy; JSON columns for
flexible per-row config (recurrence, success_keywords, new probe settings,
per-attempt records). Air-gapped, local-only.

**Testing**: pytest — `tests/contract`, `tests/integration`, `tests/unit`.
TestClient for routes; injectable `sleep_fn` already used to assert the cooldown
without real waits.

**Target Platform**: Single-host, air-gapped internal web app (Windows 11 dev;
Linux-capable). Server-rendered UI in a browser.

**Project Type**: Single project (monolithic web app under `src/asset_dashboard/`).

**Performance Goals**: Not throughput-bound. A run's duration is dominated by the
mandatory ≥5s cooldown × attempts; this is expected and surfaced via live
`running` status + polling. UI poll interval ≈ 3s (matches scan run_detail).

**Constraints**: Offline/air-gapped (Principle I) — no new network deps; probes
only reach operator-specified internal targets. Device-safety (Principle III,
v2.0.0): central guard, ≥5s cooldown non-negotiable, configurable ceiling,
stop-on-match. No secret persisted/returned (Principle II, FR-039) — username-only
disclosure. Operator-accessible (not admin-only), consistent with the existing
credential-tool routes.

**Scale/Scope**: ~5,000-host inventory; dictionaries of up to a few hundred
credentials; single-process scheduler. Within existing YAGNI envelope.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Offline-First / Air-Gapped | PASS | No new deps or network lookups; probes hit only operator-specified internal targets. HTTPS self-signed tolerance is a local-network accommodation, not an external fetch. |
| II. Security by Default | PASS | Routes remain behind auth; **no password is displayed or persisted** (username-only disclosure, FR-114); audit stays secret-free. |
| III. Device-Safety Invariants | PASS (post-amendment) | Requires the **v2.0.0 amendment** (completed): fixed 3-cap → configurable ceiling (default = dictionary size); ≥5s cooldown stays non-negotiable; central enforcement + stop-on-match retained; `inconclusive` applies only when a configured ceiling < dictionary size. See Complexity Tracking. |
| IV. Auditability | PASS | Attempt counts, timings, protocol, usernames recorded; passwords never. New events for dictionary edits already secret-free. |
| V. Testable & Independently Deliverable | PASS | Each user story (US1–US7) independently testable; updated guardrail tests assert the configurable ceiling + unchanged cooldown; background-run and form-probe get dedicated tests. |
| VI. Simplicity (YAGNI) | PASS | Reuses the single scheduler, existing models (extended), and the existing background-thread pattern; no new scheduler, broker, or service. |
| VII. Least-Privilege Roles | PASS | Credential-tool actions remain Operator-capable (parity with current routes); no admin-only surface changed. |

**Gate result**: PASS, conditional on the Principle III amendment, which has been
made (constitution v2.0.0) and is recorded in Complexity Tracking below.

## Project Structure

### Documentation (this feature)

```text
specs/008-credential-tool-fixes/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── http-api-delta.md
└── tasks.md             # Phase 2 (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
src/asset_dashboard/
├── tools/credential_tool/
│   ├── routes.py            # run/task/dictionary endpoints (extend: dict select,
│   │                        #   async run, result page route, ceiling param)
│   ├── service.py           # run_credential_check (extend: per-attempt records,
│   │                        #   ceiling, dictionary selection, status lifecycle)
│   ├── tasks.py             # dispatch_tool_task (pass dictionary + ceiling)
│   └── runner.py            # NEW: background-thread orchestrator for tool runs
│                            #   (mirrors discovery/runner.py: registry + threads)
├── compliance/
│   ├── credential_check.py  # central guard (extend: ceiling param, stop-on-match,
│   │                        #   per-attempt callback, dictionary scoping)
│   └── probes/
│       ├── base.py          # ProbeAttemptResult (extend: status/excerpt fields)
│       └── http.py          # form-aware: GET fingerprint → POST login → validate;
│                            #   https via scheme + verify=False
├── db/
│   └── models.py            # extend DefaultCredentialEntry (probe settings),
│                            #   ToolTask (dictionary_id, ceiling), ToolCheckResult
│                            #   (attempts list), ToolCheckRun (status already present)
├── config.py                # credential_check default ceiling knob (optional)
├── web/
│   ├── templates/
│   │   ├── credential_tool.html   # scheduler once/interval, dict select, layout
│   │   └── tool_run_detail.html   # NEW: scan-style per-attempt result page
│   └── i18n.py                    # new UI strings
└── scheduling/engine.py     # unchanged logic; tool-task dispatch now async-aware

tests/
├── contract/test_credential_tool.py      # dict CRUD+select, async run, result API
├── integration/test_us5_credential_tool.py  # end-to-end form probe, background run
└── unit/
    ├── test_credential_guardrails.py     # UPDATE: configurable ceiling + cooldown
    └── test_http_form_probe.py           # NEW: fingerprint→POST→validate, TLS
```

**Structure Decision**: Single project; extend the existing credential-tool
module in place. The only new files are `tools/credential_tool/runner.py`
(background execution, deliberately parallel to `discovery/runner.py`) and a
`tool_run_detail.html` result page — everything else is an extension of existing
files, honoring Principle VI (no new subsystems).

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| Amended Principle III (NON-NEGOTIABLE) — fixed 3-attempt cap → configurable ceiling (default = dictionary size) | Operator must be able to exhaustively audit a chosen default-credential dictionary (feature 008, 3.3), which a hard cap of 3 made impossible (left most dictionaries "inconclusive"). | Keeping a hard cap and only raising it to a fixed higher number was rejected: it still arbitrarily truncates larger dictionaries and the owner explicitly wanted full-dictionary coverage. The ≥5s cooldown — the invariant that actually prevents lockout timing — is retained as non-negotiable, and the ceiling stays configurable so lock-prone devices can still be protected. Amendment recorded in the constitution Sync Impact Report (v2.0.0). |
| New `tools/credential_tool/runner.py` (second background-run orchestrator) | Cred runs must become asynchronous to show `running` immediately (3.4); they have a different lifecycle than nmap scans (no subprocess, internal cooldown loop, no profile concurrency key). | Reusing `discovery/runner.py` directly was rejected: it is tightly coupled to nmap subprocess handles, `DiscoveryRun`, and profile-level concurrency; forcing tool runs through it would entangle two unrelated lifecycles. The new module mirrors its proven pattern (lock + registry + daemon thread) without a second scheduler (Principle VI preserved — scheduling stays single-engine). |

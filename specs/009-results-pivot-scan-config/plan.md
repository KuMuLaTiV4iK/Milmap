# Implementation Plan: Scan-Result Host Pivot & Run Configuration Window

**Branch**: `009-results-pivot-scan-config` | **Date**: 2026-10-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/009-results-pivot-scan-config/spec.md`

## Summary

Add a drill-down workflow on the discovery results page and replace the raw
browser target prompt with a real launch step. Operators tick host checkboxes on
a run's results (with a one-click **Select invalid-version hosts** that adds every
`non_compliant` version row — never `unknown` or `compliant` — to the current
selection, union), then pivot the selected hosts into either a **credential
check** (navigates to the existing credential-tool page with the targets
pre-filled) or **another scan with a chosen profile** (navigates to a new **Scan
Configuration page** with the targets pre-filled). That same Scan Configuration
page replaces today's `window.prompt` for every **Run now**: it is pre-filled from
the profile and lets the operator adjust, for this single run only, exactly four
fields — target, port spec, timing, and extracted fields — with a live command
preview and a **Start Scan** button; the version-validity compliance toggle and
NSE selection are inherited read-only from the saved profile. One-off edits never
touch the saved profile.

Technical approach: this is almost entirely a server-rendered-UI feature with a
small backend extension. The run-launch endpoint `POST /api/profiles/{id}/runs`
already accepts a `target_scope` override and already snapshots `params_used`;
extend its `StartRunRequest` and `discovery/runner.start_run()` to also accept
optional per-run overrides for `port_spec`, `scan_params` (timing), and
`extracted_fields`, each validated by the existing `profiles/validation.py`
allow-list validators (no raw flags ever reach nmap). Add one new page route +
template (`/profiles/{id}/scan` → `scan_config.html`) that reuses the profile
editor's four field controls and the existing `/api/profiles/preview-command`
endpoint. Everything else is template/JS edits: checkboxes + a selection toolbar
on `run_detail.html`; `?targets=` pre-fill handling on `credential_tool.html`;
and replacing `startRun()`/the prompt in `dashboard.html` and `profiles_list.html`
with a link to the new page. No new models, no migration, no new subsystem.

## Technical Context

**Language/Version**: Python 3.12 (runtime; project venv is 3.12).

**Primary Dependencies**: FastAPI + Starlette, SQLAlchemy 2.x ORM, Jinja2
server-rendered templates (htmx + vanilla JS). No new dependency.

**Storage**: SQLite (`data/app.sqlite3`) via SQLAlchemy. **No schema change** —
per-run overrides persist in the existing `DiscoveryRun.params_used` /
`profile_snapshot` JSON; host selection is ephemeral client-side state.

**Testing**: pytest — `tests/contract`, `tests/integration`, `tests/unit`;
Starlette `TestClient` for routes.

**Target Platform**: Single-host, air-gapped internal web app (Windows 11 dev;
Linux-capable). Server-rendered UI in a browser.

**Project Type**: Single project (monolithic web app under `src/asset_dashboard/`).

**Performance Goals**: Not throughput-bound. Selection and pre-fill are purely
client-side over an already-rendered results table (≤ a few thousand rows). The
measurable targets are UX ones (SC-001: subset → follow-up scan in ≤3 actions and
under 30s without retyping).

**Constraints**: Offline/air-gapped (Principle I) — no new deps, no network
lookups. Input safety — per-run overrides restricted to the same allow-listed
tunables as the profile editor; raw/free-form nmap flags rejected (FR-018). Device
safety (Principle III) — the credential pivot reuses the existing central guard
unchanged (≥5s cooldown, configurable ceiling, stop-on-match); no bypass path is
introduced. One-off semantics — launches never mutate the saved profile (FR-017).

**Scale/Scope**: ~5,000-host inventory; a run's results table is the selection
surface. Within the existing YAGNI envelope.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Offline-First / Air-Gapped | PASS | No new dependency; pure server-rendered templates + vanilla JS. No network lookups; version-validity auto-select reads findings already computed offline. |
| II. Security by Default | PASS | All new/changed routes stay behind the existing auth gate. Pivots carry only host **addresses** (not secrets) via query string. No secret is read, written, or displayed by this feature. |
| III. Device-Safety Invariants | PASS | The credential pivot **reuses the existing central guard** in `compliance/credential_check.py` exactly as-is (≥5s cooldown, operator-configurable ceiling, stop-on-match). It only pre-fills the target on the existing credential-tool run form; the operator still chooses port/service/dictionary and presses Run. No new attempt path, no bypass. Scan overrides do not touch credential checks. **No constitution change required.** |
| IV. Auditability | PASS | Scan launches already emit `RUN_STARTED` and snapshot the effective (overridden) `params_used`; credential checks launched via the pivot are the same credential-tool runs and are audited as today. The one-off target/params are therefore observable in the run record. |
| V. Testable & Independently Deliverable | PASS | US1–US4 each independently testable. New contract test for the override fields on the launch endpoint; integration tests for the three pivot/launch flows; unit test for the invalid-version selection predicate. Existing CI invariants (auth gate, duplicate-run prevention, allow-list validation) are exercised, not weakened. |
| VI. Simplicity (YAGNI) | PASS | Reuses the run-launch path, the `preview-command` endpoint, the profile-editor field controls, and the credential-tool page. The only new artifacts are one page route + `scan_config.html`. No new model, migration, scheduler, or service. |
| VII. Least-Privilege Roles | PASS | All actions are discovery actions available to both Administrator and Operator; no Administrator-only surface is touched. |

**Gate result**: PASS. No violations → Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/009-results-pivot-scan-config/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── http-api-delta.md
├── checklists/
│   └── requirements.md  # spec quality checklist (from /speckit-specify)
└── tasks.md             # Phase 2 (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
src/asset_dashboard/
├── discovery/
│   ├── routes.py            # EXTEND StartRunRequest (+ port_spec, scan_params,
│   │                        #   extracted_fields overrides) and api_start_run
│   │                        #   (validate overrides; skip cache when a param
│   │                        #   override differs from the saved profile)
│   └── runner.py            # EXTEND start_run(...): apply per-run overrides into
│                            #   params_used / profile_snapshot (no profile write)
├── profiles/
│   ├── routes.py            # NEW page route: GET /profiles/{id}/scan → scan_config
│   │                        #   page (pre-fill from profile; ?targets= overrides
│   │                        #   the target field)
│   └── validation.py        # REUSE validate_target_scope / _port_spec /
│                            #   _scan_params / _extracted_fields (no change)
├── web/
│   ├── templates/
│   │   ├── run_detail.html        # row checkboxes + selection toolbar:
│   │   │                          #   count, select-all/clear,
│   │   │                          #   "Select invalid-version hosts",
│   │   │                          #   "Scan selected with profile…" (profile
│   │   │                          #   picker → /profiles/{id}/scan?targets=),
│   │   │                          #   "Check credentials on selected"
│   │   │                          #   (→ /tools/credential-check?targets=)
│   │   ├── scan_config.html       # NEW: four editable fields + command preview
│   │   │                          #   + Start Scan (POST /api/profiles/{id}/runs
│   │   │                          #   with overrides); compliance+NSE read-only
│   │   ├── dashboard.html         # Run now → link to /profiles/{id}/scan;
│   │   │                          #   REMOVE window.prompt + startRun()
│   │   ├── profiles_list.html     # Run now → link to /profiles/{id}/scan;
│   │   │                          #   REMOVE window.prompt
│   │   └── credential_tool.html   # read ?targets= and pre-fill run_target_scope
│   └── i18n.py                    # new UI strings (toolbar actions, page title,
│                                  #   "no target"/"not evaluated" hints)
└── (no model / migration changes)

tests/
├── contract/
│   └── test_run_launch_overrides.py   # NEW: POST /runs accepts+validates
│                                      #   port_spec/scan_params/extracted overrides;
│                                      #   rejects disallowed keys; snapshot reflects
│                                      #   overrides; saved profile unchanged
├── integration/
│   └── test_results_pivot.py          # NEW: select→credential pivot prefill;
│                                      #   select→scan-config prefill→Start Scan;
│                                      #   Run now opens scan page (no prompt);
│                                      #   target-less blocked until target set
└── unit/
    └── test_invalid_version_select.py # NEW: selection predicate = non_compliant
                                       #   only (excludes unknown + compliant); union
```

**Structure Decision**: Single project; extend in place. The Scan Configuration
"window" from the spec is realized as a **page** (consistent with the clarified
"pivots navigate to the tool page" decision and reused by both Run now and the
scan pivot). The only genuinely new files are `scan_config.html` and its page
route; the launch-endpoint change is a backward-compatible extension (all new
request fields optional), so existing targeted Run-now and cache behavior is
preserved when no override is sent.

## Complexity Tracking

> No constitution violations. Section intentionally empty.

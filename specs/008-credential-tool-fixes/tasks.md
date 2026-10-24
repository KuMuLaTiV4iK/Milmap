---

description: "Task list for Credential-Check Tool Fixes"
---

# Tasks: Credential-Check Tool Fixes

**Input**: Design documents from `specs/008-credential-tool-fixes/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/http-api-delta.md, quickstart.md

**Tests**: INCLUDED — the constitution (Principle V) and spec SC-006/SC-004/SC-008 require
device-safety and no-secret-leak coverage, and existing guardrail tests must be updated to the
new configurable-ceiling behavior.

**Organization**: By user story (US1–US7 from spec.md), in priority order.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1…US7 (user-story phases only)
- Exact file paths are included in each task.

## Path Conventions

Single project: `src/asset_dashboard/…`, tests at `tests/{contract,integration,unit}/`.

---

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Verify baseline green before changes: run `python -m pytest tests/contract/test_credential_tool.py tests/unit/test_tool_scheduling.py tests/unit/test_credential_guardrails.py tests/integration/test_us5_credential_tool.py -q` and record the current pass count.

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: These shared-file changes (models, migration, base probe result, i18n) block US2–US7. Complete before starting those stories. US1 (frontend/validation only) may proceed in parallel with this phase.

- [X] T002 Amend constitution Principle III to a configurable attempt ceiling (default = selected dictionary size), keeping the ≥5s cooldown non-negotiable, in `.specify/memory/constitution.md` (v2.0.0). *(DONE during /speckit-plan.)*
- [X] T003 Extend ORM models in `src/asset_dashboard/db/models.py`:
  - `DefaultCredentialEntry`: add `probe_config: Mapped[dict] = mapped_column(JSON, default=dict)` — HTTP/HTTPS form-probe settings; empty `{}` ⇒ probe defaults; ignored by non-HTTP probes.
  - `ToolTask`: add `dictionary_id` (`String(36)`, `ForeignKey("default_credential_entries.id", ondelete="SET NULL")`, **nullable**, indexed) and `attempt_ceiling: Mapped[int | None]` (**nullable**; `null` ⇒ default = selected dictionary size).
  - `ToolCheckRun`: add `dictionary_id` (same FK, nullable, `ondelete="SET NULL"`), `attempt_ceiling: Mapped[int | None]` (nullable), and `error_detail: Mapped[str | None] = mapped_column(Text(), nullable=True)` (set when a background run fails).
- [X] T004 Add an idempotent additive migration `_add_missing_columns()` to `src/asset_dashboard/db/init.py`, called from `main()`: for each new column on `default_credential_entries`, `tool_tasks`, `tool_check_runs`, check `PRAGMA table_info(<table>)` and `ALTER TABLE <table> ADD COLUMN …` when absent (plain nullable columns; `dictionary_id` added without the FK constraint on pre-existing tables — app-side nulling covers delete, mirroring the feature-007 fix).
- [X] T005 [P] Extend `ProbeAttemptResult` in `src/asset_dashboard/compliance/probes/base.py` with `status: int | None = None` (protocol status/code for the per-attempt row; non-HTTP probes leave it `None`). Keep `response_excerpt` body-only/secret-free.
- [X] T006 Add all new UI strings in `src/asset_dashboard/web/i18n.py` (single file, additive): task-table `col_enabled` / `col_next_check`; dictionary selector label + "create a dictionary first"; probe-config field labels; result-page strings (attempts table headers, matched highlight); run-form layout labels.

**Checkpoint**: Schema, migration, probe-result field, and strings ready — US2–US7 can begin.

---

## Phase 3: User Story 1 — Correct, scan-parity scheduling (Priority: P1) 🎯 MVP

**Goal**: once/interval scheduler parity; a "once" task stays once; task table shows Enabled + Next check time.

**Independent Test**: Create a "once" task with a future time → stored/shown as one-time; table shows Enabled and Next check time columns; past "once" → 422.

- [X] T007 [US1] Contract test in `tests/contract/test_credential_tool.py`: creating `{type:"once",run_at:<future>}` persists `recurrence.type=="once"`; a past `run_at` returns `422` with a `recurrence` field error; an `interval` task computes `next_run_at`. *(Recurrence validation already exists from feature 007 — this locks it.)*
- [X] T008 [US1] Rebuild the task-form recurrence controls in `src/asset_dashboard/web/templates/credential_tool.html` to mirror `schedules.html`: a kind `<select>` (once/interval), a once group (date/hour/minute), and an interval group (every + unit).
- [X] T009 [US1] Update the task JS in `credential_tool.html`: `onTaskKindChange`, `buildTaskRecurrence` (once → `toISOString()` UTC instant; interval → `{type:'interval',every,unit}`), `editTask` (round-trip once/interval + legacy `{seconds}`), `resetTaskForm`.
- [X] T010 [US1] In the tasks table (`credential_tool.html` `loadTasks`): add an **Enabled** column (from `task.enabled`) and replace the recurrence/period column with a **Next check time** column (localized `task.next_run_at`); keep a humanized recurrence as secondary text only.

**Checkpoint**: US1 independently functional and testable.

---

## Phase 4: User Story 2 — Choose which credential dictionary to use (Priority: P1)

**Goal**: operator selects one dictionary per run/task; only that dictionary's credentials are tried.

**Independent Test**: With two dictionaries for a service, select one and confirm only its credentials are attempted; service change refreshes the selector; no dictionary ⇒ guided 422.

- [X] T011 [US2] Contract test in `tests/contract/test_credential_tool.py`: `GET /api/tools/credential-check/credentials?service=http` returns only `http` dicts; a run/task with `dictionary_id` persists it; running a service with no dictionary returns `422`.
- [X] T012 [US2] Add an optional `service` query filter to `api_list_credential_lists` in `src/asset_dashboard/tools/credential_tool/routes.py`.
- [X] T013 [US2] Add `dictionary_id: str | None` (and `attempt_ceiling: int | None`) to `RunNowIn` and `TaskIn`/`TaskUpdateIn` in `routes.py`; persist `dictionary_id`/`attempt_ceiling` onto `ToolTask` and pass `dictionary_id` into the run; reject run when the service has ≥1 dict but none chosen / none exists (`422`, message to create one).
- [X] T014 [US2] Scope candidate selection to the chosen dictionary in `src/asset_dashboard/compliance/credential_check.py` (filter `DefaultCredentialEntry` by `id == dictionary_id` when provided; fall back to service-wide only when `dictionary_id is None`). Snapshot `dictionary_id` onto the `ToolCheckRun` in `service.run_credential_check`.
- [X] T015 [US2] Add a dictionary `<select>` to the run-now and task forms in `credential_tool.html`, populated via `GET /credentials?service=` and refreshed when the service field changes.

**Checkpoint**: US1 + US2 both independently functional.

---

## Phase 5: User Story 3 — HTTP/HTTPS probes that actually authenticate (Priority: P1)

**Goal**: form-aware HTTP/HTTPS probe (GET fingerprint → POST login → status+body validation); self-signed TLS tolerated.

**Independent Test**: Against a form-login server, the probe issues `POST /login`; wrong creds → rejected (401), correct → accepted; HTTPS self-signed completes.

- [X] T016 [P] [US3] New unit test `tests/unit/test_http_form_probe.py`: GET-fingerprint then POST to `login_path`; success by `success.status`/`success.keywords`, rejection by `failure.status`; `https` path uses `verify=False`; `response_excerpt`/attempt rows contain no secret.
- [X] T017 [US3] Rewrite `src/asset_dashboard/compliance/probes/http.py` to the four-step flow using the dictionary's `probe_config` (defaults: `login_path="/login"`, `method="POST"`, `username_field="username"`, `password_field="password"`, `encoding="form"`, `success={status:[200,302],keywords:success_keywords}`, `failure={status:[401,403]}`): GET fingerprint (capture status/body/optional CSRF token per `probe_config.csrf`), POST credential, evaluate success = `success` matched AND NOT `failure`; populate `ProbeAttemptResult.status` + secret-free `response_excerpt`. HTTPS = same via `scheme="https"` with `httpx` `verify=False`. The probe still performs exactly ONE authentication attempt per call (the loop/cooldown stays central).
- [X] T018 [US3] Add `probe_config` to `CredentialListIn` in `routes.py` with validation (object; `method ∈ {GET,POST}`, `encoding ∈ {form,json}` when present ⇒ else `422 {fields:{probe_config}}`); include `probe_config` in `_serialize_credential_list`.
- [X] T019 [US3] Add `probe_config` inputs to the dictionary form in `credential_tool.html` (login path, method, field names, success/failure status + keywords, optional fingerprint/CSRF) with JS to assemble/parse the object; empty ⇒ omit so defaults apply.

**Checkpoint**: US3 independently functional (HTTP/HTTPS checks real creds).

---

## Phase 6: User Story 4 — Exhaustive, cooldown-guarded attempts (Priority: P1)

**Goal**: try the whole chosen dictionary under a configurable ceiling (default = dict size), ≥5s cooldown, stop-on-match; exhausted-no-match ⇒ compliant; ceiling<dict-size hit ⇒ inconclusive.

**Independent Test**: Dictionary of N with k-th valid → exactly k attempts, ≥5s apart, stop at k; none valid → all N tried, compliant; ceiling=k-1, no match → inconclusive.

- [X] T020 [US4] Update `tests/unit/test_credential_guardrails.py`: replace the hard-max-3 assertions with — ceiling defaults to dictionary size; stop-on-match stops further attempts; consecutive attempts ≥ `credential_check_cooldown_seconds` apart (injected `sleep_fn` call count/arg); exhausted-no-match ⇒ `compliant`; configured `attempt_ceiling` < dict size with no match ⇒ `inconclusive`.
- [X] T021 [US4] Refactor `check_default_credentials` in `src/asset_dashboard/compliance/credential_check.py`: accept `ceiling: int | None` (default = number of candidates) and an optional per-attempt sink; enforce `attempts_made < effective_ceiling`; keep the ≥5s cooldown between consecutive attempts (non-negotiable); **stop on first match** (`non_compliant`); exhausted-all-candidates-no-match ⇒ `compliant`; ceiling reached below candidate count with no match ⇒ `inconclusive`. Record per-attempt `{username, status, excerpt, matched}` (never the secret).
- [X] T022 [US4] In `src/asset_dashboard/tools/credential_tool/service.py`, pass the effective `attempt_ceiling` (run/task value or default), persist per-attempt records + `matched_username`/`matched_dictionary_entry` into `ToolCheckResult.detail` (password-free), and keep `attempts_made`.

**Checkpoint**: US4 independently functional; US3+US4 together give correct HTTP auditing.

---

## Phase 7: User Story 5 — Live run status (Priority: P2)

**Goal**: a started check appears as `running` immediately and polls to `completed`/`failed`.

**Independent Test**: Start a multi-target run → visible as `running` at once → `completed` via polling; forced worker error → `failed` with `error_detail`, never stuck.

- [X] T023 [US5] Integration test in `tests/integration/test_us5_credential_tool.py`: `POST /api/tools/credential-check` returns `{status:"running"}` and the run exists as `running` before completion; it transitions to `completed`; a forced failure yields `failed` with non-null `error_detail`.
- [X] T024 [US5] New `src/asset_dashboard/tools/credential_tool/runner.py` mirroring `discovery/runner.py`: module lock + running-run registry, commit the `ToolCheckRun` as `running`, run the probing loop on a daemon thread, finishers set `completed`/`failed` (with `error_detail`) in a fresh `session_scope`, clear registry, `archive_oldest`. No second scheduler.
- [X] T025 [US5] Rework `src/asset_dashboard/tools/credential_tool/service.py` so the synchronous loop body is callable from the background worker; `routes.api_run_now` starts the run via `runner` and returns `{run_id, status:"running"}`; `tasks.dispatch_tool_task` dispatches through the runner too.
- [X] T026 [US5] In `credential_tool.html`, poll `loadRuns()` (~3s) while any run is `running` so history updates to `completed`/`failed` without a manual refresh.

**Checkpoint**: US5 functional; runs are observable live.

---

## Phase 8: User Story 6 — Rich result window (Priority: P2)

**Goal**: scan-style per-attempt result page; matched row highlighted by username; no password anywhere.

**Independent Test**: Open a finished run's result page → table of attempts (target, username, response, result) with the matched row highlighted; the known secret appears nowhere in page/JSON/audit.

- [X] T027 [US6] Contract test in `tests/contract/test_credential_tool.py`: `GET /runs/{id}` includes `attempts: [{username,status,excerpt,matched}]`, `matched_username`, `attempt_ceiling`, `error_detail`, and `status` may be `running`; assert the attempted secret string is absent from the entire response (FR-114).
- [X] T028 [US6] Extend `_serialize_run_detail` (and `_serialize_run`) in `routes.py` to surface `attempts`, `matched_username`, `matched_dictionary_entry`, `dictionary_id`, `attempt_ceiling`, and `error_detail` — password-free.
- [X] T029 [US6] New server-rendered page `src/asset_dashboard/web/templates/tool_run_detail.html` styled like `run_detail.html`: per-target attempts table (target, username, response status/excerpt, result) with the matched row highlighted and labelled by username + dictionary entry; add the `GET /tools/credential-check/runs/{run_id}` page route in `routes.py` (`pages_router`) and confirm it is included in `main.py`.
- [X] T030 [US6] In `credential_tool.html`, replace the `showRun` `alert()` with a link/navigation to the new result page; while `status == running` the result page polls (~3s) and shows partial progress.

**Checkpoint**: US6 functional; results are diagnosable and secret-free.

---

## Phase 9: User Story 7 — Run-form & dictionary layout polish (Priority: P3)

**Goal**: run-now controls on two rows; wide dictionary description field.

**Independent Test**: Run-now card shows target on row 1 and port+service+dictionary+start on row 2; dictionary description field is full width.

- [X] T031 [US7] In `credential_tool.html`, lay out the run-now card as target on row 1 and port + service + dictionary + start button in one flex row beneath it (reuse existing CSS utilities; add minimal CSS in `src/asset_dashboard/web/static/base.css` only if needed).
- [X] T032 [US7] Make the dictionary description/vendor input full width in `credential_tool.html` (`style="width:100%"` / existing wide-field class).

**Checkpoint**: All user stories independently functional.

---

## Phase 10: Polish & Cross-Cutting Concerns

- [X] T033 [P] Update `data/reference/default_credentials.json` to include example `probe_config` blocks for the `http` and `https` dictionaries (login path, field names, success/failure), so a fresh `seed_reference` demonstrates the form probe.
- [X] T034 [P] Security assertion test in `tests/unit/` (or extend T027): scan a completed run's result JSON, the audit log entries, and the rendered result page for any attempted secret string; assert absent (FR-114 / SC-006).
- [X] T035 Run the full suite `python -m pytest -q` and walk quickstart.md scenarios A–G; fix regressions (watch the feature-007 delete test and `test_tool_scheduling.py`).
- [X] T036 [P] Verify the constitution re-check holds in code: a dedicated test asserts the ≥5s cooldown is still enforced and the ceiling defaults to dict size (keeps SC-008/002 SC-006 observable).

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (P1)**: none.
- **Foundational (P2)**: after Setup; **blocks US2–US7**. US1 may run alongside Foundational (it touches no new model/schema).
- **User stories (P3+)**: after Foundational.
  - US1 (P1) — independent (frontend/validation only).
  - US2 (P1) — needs T003 (`dictionary_id`, `attempt_ceiling`).
  - US3 (P1) — needs T003 (`probe_config`) + T005 (`ProbeAttemptResult.status`).
  - US4 (P1) — needs T005 (status in per-attempt rows); builds the attempt-loop that US6 renders.
  - US5 (P2) — needs T003 (`error_detail`) + US4's refactored service body.
  - US6 (P2) — needs US4 (per-attempt `detail`) + T003 fields.
  - US7 (P3) — independent (layout only).
- **Polish (P10)**: after the desired stories.

### Shared-file ordering (not parallel across stories)

`credential_tool.html` is touched by US1, US2, US3, US6, US7 → sequence those edits (don't parallelize across stories). `routes.py`, `service.py`, and `credential_check.py` are touched by US2/US3/US4/US5/US6 → follow the phase order (US2 → US3 → US4 → US5 → US6).

### Within a story

Test first (where listed) → model/route/probe → template/JS → integration.

### Parallel opportunities

- T005 and T006 (Foundational) are `[P]` (different files) once T003 is in.
- T016 (US3 unit test) is `[P]` with other files.
- Polish T033, T034, T036 are `[P]`.
- With multiple developers after Foundational: US1 and US7 (frontend-only, independent) can go in parallel with the US2→US6 backend chain.

---

## Parallel Example: Foundational

```bash
# After T003 (models) lands, these touch different files:
Task: "T005 Extend ProbeAttemptResult in compliance/probes/base.py"
Task: "T006 Add new i18n strings in web/i18n.py"
```

---

## Implementation Strategy

### MVP scope

Two viable MVPs depending on intent:

- **Smallest honest fix**: Setup + Foundational + **US1** (scheduling parity + columns) — resolves the most visible breakage (once→interval) with no backend risk.
- **Core-value MVP (recommended)**: Setup + Foundational + **US2 + US3 + US4** — makes the credential check actually correct (right dictionary, real HTTP auth, exhaustive+safe attempts). US5/US6 then make it observable and diagnosable; US7 is polish.

### Incremental delivery

1. Setup + Foundational → schema/strings ready.
2. US1 → validate scheduling → demo.
3. US2 → US3 → US4 → validate correct checking → demo (core value).
4. US5 → live status; US6 → result window; US7 → polish. Each is independently testable.

---

## Notes

- `[P]` = different files, no dependency on an incomplete task.
- Keep every per-attempt record and audit entry **password-free** (FR-114) — usernames only.
- The ≥5s cooldown is non-negotiable; only the attempt ceiling is configurable (constitution v2.0.0).
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.

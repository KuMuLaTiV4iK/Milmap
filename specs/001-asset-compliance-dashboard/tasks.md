---
description: "Task list for Asset Inventory & Compliance Management Dashboard"
---

# Tasks: Asset Inventory & Compliance Management Dashboard

**Input**: Design documents from `/specs/001-asset-compliance-dashboard/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/http-api.md, quickstart.md

**Tests**: Included. This is a security/compliance tool whose correctness depends on invariants (auth gate, ≥20-char policy, ≤3-attempt/≥5 s-cooldown credential guardrails, offline version checks, no duplicate runs). The spec Success Criteria and quickstart explicitly require these be asserted, so test tasks are generated for them.

**Organization**: Tasks are grouped by the six user stories from spec.md so each can be implemented and tested independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1–US6 (user-story phases only)
- Paths follow the single-project web-app layout in plan.md (`src/asset_dashboard/...`)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, air-gapped dependency provisioning, structure.

- [X] T001 Create project structure per plan.md (`src/asset_dashboard/{auth,profiles,discovery,compliance,history,scheduling,audit,db,web}`, `data/reference/`, `tests/{unit,integration,contract}`)
- [X] T002 Define pinned dependencies in `pyproject.toml` + `requirements.lock` (FastAPI, Uvicorn, Jinja2, SQLAlchemy 2.x, Alembic, APScheduler, argon2-cffi, pydantic v2, python-libnmap, paramiko, httpx, telnetlib3) and document the offline `uv pip install --no-index --find-links wheelhouse` flow
- [X] T003 [P] Configure linting/formatting (ruff + black) and `pytest.ini`/`pyproject` test config
- [X] T004 [P] Vendor HTMX + base CSS into `src/asset_dashboard/web/static/` (no CDN references)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST complete before ANY user story.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 Implement settings in `src/asset_dashboard/config.py` (data paths, session idle timeout, default `cache_freshness_seconds`, global run-concurrency cap, sign-in throttle threshold, credential-check limits: max_attempts=3, cooldown_seconds=5)
- [X] T006 Setup SQLAlchemy 2.x engine/session with SQLite WAL mode in `src/asset_dashboard/db/base.py`
- [X] T007 Initialize Alembic migrations framework wired to `db/base.py`
- [X] T008 Create ASGI app factory + Uvicorn entry with startup/shutdown (scheduler lifecycle) in `src/asset_dashboard/main.py`
- [X] T009 [P] Implement `AuditLogEntry` model + append helper in `src/asset_dashboard/audit/log.py` (`event_type` enum: signin_success, signin_failure, lockout, profile_change, run_started, run_finished, compliance_check, schedule_change, account_change; `detail` json; MUST never store secrets, FR-006/FR-039)
- [X] T010 [P] Base Jinja2 layout template + static asset wiring in `src/asset_dashboard/web/templates/base.html`
- [X] T011 Implement auth-gate middleware in `src/asset_dashboard/auth/sessions.py`: every path except `GET /login` and `POST /api/auth/login` requires a session → `401` (JSON) / redirect (HTML), disclosing no data (FR-001)
- [X] T012 Implement CSRF protection for state-changing posts and the JSON error shape `{error:{code,message,fields?}}` in `src/asset_dashboard/web/errors.py`

**Checkpoint**: Foundation ready — user stories can begin.

---

## Phase 3: User Story 1 - Secure local access (Priority: P1) 🎯 MVP

**Goal**: No access without authentication; enforce ≥20-char password policy; throttle brute force; idle-timeout sessions; audit security events.

**Independent Test**: Unauthenticated requests are blocked with no data disclosed; a <20-char password is rejected at create and change; valid sign-in yields a session; repeated failures throttle; idle session forces re-auth.

### Tests for User Story 1 ⚠️ (write first, ensure they FAIL)

- [X] T013 [P] [US1] Contract test for `/api/auth/*` and `/api/accounts/*` in `tests/contract/test_auth.py` (401 on gated paths, 422 on short password, 429 on throttle)
- [X] T014 [P] [US1] Unit test password policy — rejects length < 20 at creation AND change (FR-002) in `tests/unit/test_password_policy.py`
- [X] T015 [P] [US1] Integration test for US1 journey (gate, throttle, idle timeout) in `tests/integration/test_us1_access.py`

### Implementation for User Story 1

- [X] T016 [P] [US1] `OperatorAccount` model in `src/asset_dashboard/db/models.py` (`username` string unique required; `password_hash` Argon2id — never plaintext/recoverable, FR-003; `status` enum active/disabled; `failed_attempts` int; `lock_until` datetime nullable)
- [X] T017 [P] [US1] Argon2id hashing + password policy (length ≥ 20, FR-002) in `src/asset_dashboard/auth/passwords.py`
- [X] T018 [US1] Sign-in throttle/lockout after configurable consecutive failures, setting `lock_until` (FR-004) in `src/asset_dashboard/auth/throttle.py`
- [X] T019 [US1] Server-side sessions with configurable idle timeout + explicit sign-out (FR-005) in `src/asset_dashboard/auth/sessions.py`
- [X] T020 [US1] Auth + account routes in `src/asset_dashboard/auth/routes.py` (login/logout/create account/change password; 422 on policy failure keeps old credential in force)
- [X] T021 [US1] Login HTML page + account management templates in `src/asset_dashboard/web/templates/`
- [X] T022 [US1] CLI `create_account` helper (`python -m asset_dashboard.auth.create_account`) for first-operator bootstrap (quickstart)
- [X] T023 [US1] Emit audit events for signin_success/failure, lockout, account_change (FR-006)

**Checkpoint**: Auth gate fully functional and independently testable (SC-001, SC-002).

---

## Phase 4: User Story 2 - Define & manage Asset Discovery Profiles (Priority: P1)

**Goal**: Full CRUD of profiles with validated scan parameters, telemetry-field selection, host-management link templates, and edit-conflict detection.

**Independent Test**: Create "VoIP Infrastructure Audit" (ports 5060-5062), edit/duplicate/delete it; malformed targets or disallowed scan flags are rejected; a stale save is rejected with 409.

### Tests for User Story 2 ⚠️

- [X] T024 [P] [US2] Contract test for `/api/profiles*` in `tests/contract/test_profiles.py` (CRUD, 422 validation, 409 stale `version_token`)
- [X] T025 [P] [US2] Unit test scan-param allow-list + target/port parsing (FR-011) in `tests/unit/test_profile_validation.py`
- [X] T026 [P] [US2] Integration test create/edit/duplicate/delete flow in `tests/integration/test_us2_profiles.py`

### Implementation for User Story 2

- [X] T027 [P] [US2] `DiscoveryProfile` model in `src/asset_dashboard/db/models.py` (`name` unique required; `target_scope` json hosts/ranges/subnets; `port_spec` string e.g. `5060-5062`; `scan_params` json allow-listed only; `extracted_fields` json MUST allow ≥ open_ports + service/firmware version, FR-012; `compliance_settings` json; `cache_freshness_seconds` int; `version_token` int optimistic-concurrency)
- [X] T028 [P] [US2] `HostLinkTemplate` model in `src/asset_dashboard/db/models.py` (`url_template` MUST contain `{host}` placeholder, FR-013)
- [X] T029 [US2] Scan-param allow-list + target/port validation in `src/asset_dashboard/profiles/validation.py` (permit only timing `-T0..-T5`, port spec, `-sV` intensity, `--max-rate`, `--host-timeout`, discovery toggles; reject raw/free-form flags → prevents command injection, FR-011)
- [X] T030 [US2] Profile service: CRUD + duplicate + optimistic concurrency (increment `version_token`; stale save → 409, no silent overwrite, FR-042) in `src/asset_dashboard/profiles/service.py`
- [X] T031 [US2] Profile routes (GET/POST/PUT/DELETE/duplicate; delete removes from active use but retains historical runs, FR-027) in `src/asset_dashboard/profiles/routes.py`
- [X] T032 [US2] Profile list + editor templates (incl. host-link and compliance-settings config) in `src/asset_dashboard/web/templates/`

**Checkpoint**: Profiles round-trip with validation + conflict detection (SC-003).

---

## Phase 5: User Story 3 - Run discovery & review results (Priority: P1)

**Goal**: Orchestrate nmap per profile, extract telemetry, present a results table with clickable host-management links; support cancel; distinguish empty vs failed.

**Independent Test**: Run a profile → results table shows open ports + versions per host with working management links; cancel retains partial results; empty range → `hosts=0`; missing nmap → `failed` with detail.

### Tests for User Story 3 ⚠️

- [X] T033 [P] [US3] Contract test for `/api/profiles/{id}/runs`, `/api/runs/*` in `tests/contract/test_runs.py` (202/200-cache/409/503; cancel; results; empty vs failed)
- [X] T034 [P] [US3] Unit test nmap XML → results parser in `tests/unit/test_nmap_parser.py`
- [X] T035 [P] [US3] Integration test run→results with host links, cancel, empty result, nmap-missing failure in `tests/integration/test_us3_discovery.py`

### Implementation for User Story 3

- [X] T036 [P] [US3] `DiscoveryRun` model in `src/asset_dashboard/db/models.py` (`profile_id` FK nullable; `profile_snapshot` json survives deletion; `trigger` enum manual/scheduled; `status` enum running/completed/cancelled/failed; `served_from_cache` bool + `source_run_id` FK nullable; `params_used` json; `summary` json; `error_detail` text nullable; index `(profile_id, started_at)`)
- [X] T037 [P] [US3] `DiscoveredAsset` model in `src/asset_dashboard/db/models.py` (`address`; `state` enum up/down/no_response; `open_ports` json [{port,protocol,service,version}]; `extracted` json; `management_link` string nullable → null shows unavailable, FR-019; index `(run_id)`)
- [X] T038 [US3] nmap subprocess runner (XML `-oX -`, start + cancel via process-group terminate) in `src/asset_dashboard/discovery/nmap_runner.py`
- [X] T039 [US3] nmap XML → structured results parser (libnmap, stdlib fallback) in `src/asset_dashboard/discovery/parser.py`
- [X] T040 [US3] Run lifecycle orchestrator in `src/asset_dashboard/discovery/runner.py`: global concurrency limiter (503 when exceeded, FR-021), one `running` run per profile (409, FR-043), status transitions, nmap missing/underprivileged → `failed` + `error_detail` (FR-020), empty → `hosts=0` (distinct from failed)
- [X] T041 [US3] Host-management link resolution from `HostLinkTemplate` (null when unresolvable, FR-019) in `src/asset_dashboard/discovery/runner.py`
- [X] T042 [US3] Run routes (start/cancel/get/results) in `src/asset_dashboard/discovery/routes.py`
- [X] T043 [US3] Live-run + results-table template with clickable host links in `src/asset_dashboard/web/templates/`
- [X] T044 [US3] Emit audit run_started/run_finished (FR-006)

**Checkpoint**: Discovery → results → one-click host page works (SC-004). **P1 trio (US1+US2+US3) = usable MVP.**

---

## Phase 6: User Story 4 - Historical runs & result caching (Priority: P2)

**Goal**: Persist every run; history panel newest-first; freshness-window cache reuse + force-fresh; retention policy.

**Independent Test**: Re-run within the window returns a cached result (no new scan); force-fresh supersedes it; history lists both with timestamps/params and opens full captured results.

### Tests for User Story 4 ⚠️

- [X] T045 [P] [US4] Contract test `/api/history*` + cache-hit vs force-fresh behavior in `tests/contract/test_history.py`
- [X] T046 [P] [US4] Integration test cache reuse within window + force-fresh + history detail in `tests/integration/test_us4_history.py`

### Implementation for User Story 4

- [X] T047 [US4] History service: list runs newest-first with timestamp/profile/params/status/summary (FR-022, FR-023) in `src/asset_dashboard/history/service.py`
- [X] T048 [US4] Freshness-window cache in `src/asset_dashboard/history/cache.py` (reuse latest completed run within `cache_freshness_seconds`, set `served_from_cache`+`source_run_id`, label with original time; `force_fresh` bypasses, FR-024/FR-025)
- [X] T049 [US4] Configurable retention policy — predictable prune; profile deletion retains runs (FR-026/FR-027) in `src/asset_dashboard/history/service.py`
- [X] T050 [US4] History panel + run-detail templates (target history load < 3 s at ~5,000 hosts, SC-012) in `src/asset_dashboard/web/templates/`

**Checkpoint**: History + caching independently functional (SC-005, SC-006).

---

## Phase 7: User Story 5 - Scheduled discovery jobs (Priority: P2)

**Goal**: Recurring auto-runs with next-run display, overlap prevention, and catch-up handling.

**Independent Test**: Attach a schedule → next-run shown → it triggers a recorded run; overlap with an in-progress run produces no duplicate; missed-while-down follows catch-up policy.

### Tests for User Story 5 ⚠️

- [X] T051 [P] [US5] Contract test `/api/profiles/{id}/schedule` in `tests/contract/test_schedule.py`
- [X] T052 [P] [US5] Integration test trigger→run, overlap skip/queue, catch-up on restart in `tests/integration/test_us5_schedule.py`

### Implementation for User Story 5

- [X] T053 [P] [US5] `Schedule` model in `src/asset_dashboard/db/models.py` (`profile_id` FK unique; `recurrence` json cron/interval; `enabled` bool; `next_run_at` datetime; `overlap_policy` enum skip/queue default skip; `catch_up_policy` enum run_once/skip; `last_triggered_at` nullable)
- [X] T054 [US5] APScheduler engine + SQLAlchemy job store in `src/asset_dashboard/scheduling/engine.py` (produce a DiscoveryRun identical to manual honoring caching, FR-030; overlap policy prevents duplicate concurrent run, FR-031/FR-043; catch-up on startup, FR-032) — implemented as our own `Schedule` table + `tick()` due-scan (directly testable), with APScheduler used only as the periodic heartbeat calling `tick()`
- [X] T055 [US5] Schedule routes GET/PUT/DELETE computing `next_run_at` (FR-029) in `src/asset_dashboard/scheduling/routes.py`
- [X] T056 [US5] Schedule management template + audit schedule_change in `src/asset_dashboard/web/templates/`

**Checkpoint**: Scheduling independently functional, no duplicate runs (SC-007).

---

## Phase 8: User Story 6 - Compliance auditing (Priority: P2)

**Goal**: Offline version/firmware validity + guarded default-credential check (real, bounded auth confirmed by response-body keyword match).

**Independent Test**: VoIP profile run flags versions valid/invalid/unknown with zero network calls; default-credential check confirms via keyword match, never exceeds 3 attempts/target, waits ≥5 s between attempts, flags compliant/non_compliant/inconclusive, stores no secrets.

### Tests for User Story 6 ⚠️

- [X] T057 [P] [US6] Unit test credential guardrail INVARIANTS in `tests/unit/test_credential_guardrails.py`: `attempts_made ≤ 3` per target, consecutive attempts ≥ 5 s apart, cap-without-match → `inconclusive` (FR-037/FR-038, SC-008)
- [X] T058 [P] [US6] Unit test response-body keyword/signature match AND offline version check performs ZERO network I/O (FR-034/FR-036a, SC-009) in `tests/unit/test_compliance.py`
- [X] T059 [P] [US6] Integration test VoIP compliance: version valid/invalid/unknown + credential compliant/non_compliant/inconclusive in `tests/integration/test_us6_compliance.py`

### Implementation for User Story 6

- [X] T060 [P] [US6] `ComplianceFinding` model in `src/asset_dashboard/db/models.py` (`control` enum version_validity/default_credentials; `result` enum compliant/non_compliant/unknown/inconclusive; `detail` json — MUST NOT store attempted secret recoverably, FR-039)
- [X] T061 [P] [US6] `ReferenceVersionEntry` + `DefaultCredentialEntry` models in `src/asset_dashboard/db/models.py` (`service` enum sip/ssh/http/telnet; `success_keywords` json; `credentials` handled in-memory only)
- [X] T062 [P] [US6] Seed files `data/reference/version_validity.json` + `data/reference/default_credentials.json` (JSON, not YAML — stdlib-only, no new dependency) and `python -m asset_dashboard.db.seed_reference` loader
- [X] T063 [US6] Offline version-validity check in `src/asset_dashboard/compliance/version_check.py` (exact + range match; not-in-dataset → `unknown`, FR-035; ZERO external/network I/O, FR-034)
- [X] T064 [US6] Probe base contract + response-body keyword match in `src/asset_dashboard/compliance/probes/base.py`
- [X] T065 [P] [US6] SIP probe (REGISTER/OPTIONS over raw UDP/TCP, ports 5060-5062) in `src/asset_dashboard/compliance/probes/sip.py`
- [X] T066 [P] [US6] SSH probe (paramiko) in `src/asset_dashboard/compliance/probes/ssh.py`
- [X] T067 [P] [US6] HTTP probe (httpx, local addresses only) in `src/asset_dashboard/compliance/probes/http.py`
- [X] T068 [P] [US6] Telnet probe (raw socket login exchange — `telnetlib` removed in Python 3.13+, and its async-only replacement `telnetlib3` would mix awkwardly with these otherwise-synchronous probes) in `src/asset_dashboard/compliance/probes/telnet.py`
- [X] T069 [US6] Central guarded credential-check orchestrator in `src/asset_dashboard/compliance/credential_check.py`: enforce `max_attempts=3` per target and `cooldown_seconds=5` between attempts CENTRALLY (not per-probe); keyword match → `non_compliant`; no match within cap → `compliant`; cap hit without conclusive result → `inconclusive` (FR-036/FR-037/FR-038/FR-039)
- [X] T070 [US6] Wire compliance into run pipeline (findings in `results[].findings` + run `summary`); audit compliance_check with attempt counts/timings and NO secrets (FR-033, SC-008) in `src/asset_dashboard/discovery/runner.py` + new `compliance/evaluate.py`
- [X] T071 [US6] Compliance display in results table + dashboard "last-run posture" view (SC-010, SC-011) in `src/asset_dashboard/web/templates/` + new `web/dashboard.py`

**Checkpoint**: Compliance auditing independently functional with guardrails verified (SC-008–SC-011).

---

## Phase 9: Polish & Cross-Cutting Concerns

- [X] T072 [P] Run full `quickstart.md` validation end-to-end — `db.init`/`seed_reference` verified against an isolated temp DB; `auth.create_account` + full login verified live by the operator on their own real deployment; all US1-US6 scenarios covered by the automated suite. Not exercised: a real `nmap` binary (none available in the dev sandbox) — all discovery/compliance behavior is verified against mocked process output instead.
- [X] T073 [P] Wire the CI invariant suite (auth gate 100%, ≥20-char policy, credential guardrails, offline version check, no duplicate runs, optimistic concurrency) per quickstart "Key invariants" — `.github/workflows/ci.yml` runs ruff + the full pytest suite on push/PR (inert until this becomes a pushed git repo; no `git init` was run, since that's the operator's call)
- [X] T074 [P] Operator/admin docs + README — `README.md` at repo root (not `docs/`: no other docs existed yet, so a single root README covers setup/operation/layout/security notes)
- [X] T075 Security hardening pass — security-response-headers middleware (`web/security_headers.py`); secret-handling re-verified (audit log rejects secret-like keys, credential-check findings never carry the attempted secret); **found and fixed a real correctness bug**: the SIP probe sent the password as a raw `Authorization: response=` value instead of performing the actual RFC 2617 digest challenge/response (including the `qop="auth"` variant real servers use) — it would have produced false negatives against any real SIP server. Rewritten and pinned to the authoritative RFC 2617 §3.5 worked example.
- [X] T076 Performance validation at ~5,000 hosts and a /22 run; confirm history loads < 3 s (SC-012) — `tests/unit/test_performance_scale.py` seeds 5,120 hosts across 5 runs and confirms both the service-layer query and the full HTTP round-trip complete in well under 1s, comfortably inside the 3s budget.
- [X] T077 Code cleanup/refactor across packages — `ruff check src/ tests/` fully clean (0 errors); modernized `(str, enum.Enum)` → `enum.StrEnum`; removed redundant per-call `utcnow` imports; also found and fixed two real test-isolation bugs along the way: the session-signing secret key and the APScheduler heartbeat were both leaking into/across tests via process-wide singletons untouched by the per-test DB-swap, the second of which was the root cause of an intermittent background-thread DB race (see `tests/conftest.py`).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (P1)**: no dependencies.
- **Foundational (P2)**: depends on Setup — BLOCKS all user stories.
- **User Stories (P3–P8)**: all depend on Foundational.
  - US1, US2 (both P1) are independent of each other after Foundational.
  - US3 (P1) depends on US2 (needs a profile to run) + reuses US1 auth.
  - US4 (P2) depends on US3 (persists/reuses runs).
  - US5 (P2) depends on US3 (produces runs) — independent of US4.
  - US6 (P2) depends on US3 (findings attach to run results) — independent of US4/US5.
- **Polish (P9)**: after the desired stories are complete.

### Within Each User Story

- Tests written first and failing → Models → Services → Routes → Templates → Audit wiring.

### Parallel Opportunities

- Setup: T003, T004 in parallel.
- Foundational: T009, T010 in parallel (after T006).
- Each story's `[P]` tests run together; `[P]` models in the same `models.py` are logically parallel but edit one file — serialize the actual writes.
- Probes T065–T068 are genuinely parallel (separate files).
- After Foundational, with staff: US1 ∥ US2, then US3; US4/US5/US6 can proceed in parallel once US3 lands.

---

## Parallel Example: User Story 6 probes

```bash
Task: "SIP probe in src/asset_dashboard/compliance/probes/sip.py"
Task: "SSH probe in src/asset_dashboard/compliance/probes/ssh.py"
Task: "HTTP probe in src/asset_dashboard/compliance/probes/http.py"
Task: "Telnet probe in src/asset_dashboard/compliance/probes/telnet.py"
```

---

## Implementation Strategy

### MVP

- **Minimal first increment**: US1 (secure access) — validate the auth gate and password policy independently.
- **Usable MVP**: the P1 trio **US1 + US2 + US3** — sign in, define a profile, run discovery, and read results with host links. This is the smallest end-to-end valuable product.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. US1 → US2 → US3 → **usable MVP**; validate and demo.
3. US4 (history/caching) → US5 (scheduling) → US6 (compliance), each tested and demoed independently.

### Parallel Team Strategy

After Foundational: Dev A on US1, Dev B on US2 (then US3 once US2 model lands); once US3 is in, US4/US5/US6 split across devs.

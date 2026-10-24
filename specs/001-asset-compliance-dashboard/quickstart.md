# Quickstart & Validation Guide: Asset Inventory & Compliance Management Dashboard

**Date**: 2026-10-21 | **Feature**: `001-asset-compliance-dashboard`

This guide shows how to run the application and validate each spec user story end-to-end. It is a **validation/run guide** — implementation code lives in `src/` (see `plan.md` structure) and is produced during the implementation phase. Endpoint/field details are in [contracts/http-api.md](./contracts/http-api.md) and [data-model.md](./data-model.md).

## Prerequisites

- **Host**: Windows 11 (confirmed) or Linux, on an isolated/air-gapped segment.
- **Python**: 3.15 (the repo `.venv` already exists).
- **nmap**: installed on the host and on `PATH`, with privileges sufficient for the configured scan types (spec Assumption). Verify: `nmap --version`.
- **Offline dependencies**: a local wheelhouse (no internet). Reference datasets present under `data/reference/`.
- **Test targets**: lab/authorized internal hosts only. For the VoIP example, a SIP endpoint reachable on 5060–5062.

## Setup (air-gapped)

```powershell
# From repo root (D:\MITIT\Milmap)
# 1. Install pinned deps from the local wheelhouse into the existing venv (no internet)
uv pip install --no-index --find-links .\wheelhouse -r requirements.lock

# 2. Initialize the database and seed offline reference data
.\.venv\Scripts\python -m asset_dashboard.db.init          # create schema (Alembic)
.\.venv\Scripts\python -m asset_dashboard.db.seed_reference # load version_validity + default_credentials

# 3. Create the first operator account (password must be >= 20 chars)
.\.venv\Scripts\python -m asset_dashboard.auth.create_account --username admin

# 4. Run the app (local only)
.\.venv\Scripts\python -m asset_dashboard.main   # serves http://127.0.0.1:8000
```

Open `http://127.0.0.1:8000` in a local browser.

## Automated test suites

```powershell
.\.venv\Scripts\python -m pytest tests/unit            # policy, param validation, keyword match, guardrails
.\.venv\Scripts\python -m pytest tests/integration     # per-user-story flows
.\.venv\Scripts\python -m pytest tests/contract        # HTTP API conformance vs contracts/http-api.md
```

---

## Validation scenarios (map to spec user stories)

### US1 — Secure local access (P1)
1. With no session, request `GET /` → redirected to `/login`; request `GET /api/profiles` → `401`, **no data disclosed**. (FR-001)
2. Create an account with a 12-char password → rejected `422` on `password`; with a ≥20-char password → `201`. (FR-002)
3. Sign in with valid credentials → dashboard loads. (FR-001)
4. Submit wrong password past the configured threshold → `429` throttled; event in audit log. (FR-004, FR-006)
5. Leave the session idle past the timeout → next action forces re-auth. (FR-005)
- **Pass**: all of the above; `SC-001`, `SC-002` hold.

### US2 — Define & manage profiles (P1)
1. Create profile **"VoIP Infrastructure Audit"**: target an authorized subnet, `port_spec = 5060-5062`, `-sV` enabled, select fields (open_ports, service version), add a host link `https://{host}/` , enable `default_credentials (sip)` + `version_validity`. → `201`. (FR-007–FR-013)
2. Submit a profile with a malformed target or a disallowed scan flag → `422` with the offending field. (FR-011)
3. Edit the profile; duplicate it; delete the duplicate. → each persists; original untouched. (FR-007)
- **Pass**: profile round-trips; validation rejects bad input; `SC-003` (create < 5 min) achievable.

### US3 — Run discovery & review results (P1)
1. `POST /api/profiles/{id}/runs` → `202 running`; poll `GET /api/runs/{id}` to `completed`. (FR-016)
2. `GET /api/runs/{id}/results` → table rows with open ports + versions; each row has a clickable `management_link`; a host with no page shows link unavailable (row still renders). (FR-018, FR-019)
3. Start a run and `POST /api/runs/{id}/cancel` → `cancelled` with partial results retained. (FR-017)
4. Point a profile at an empty range → `completed` with `summary.hosts = 0` (not `failed`); temporarily rename/remove nmap → run `failed` with `error_detail`. (FR-020)
- **Pass**: `SC-004` (one-click to host page) holds.

### US4 — History & caching (P2)
1. Run the profile, then immediately request another run **without** force-fresh within the freshness window → response `200 served_from_cache=true` referencing `source_run_id`; **no new network scan**. (FR-024)
2. Request again with `force_fresh=true` → a fresh `running` run supersedes the cache. (FR-025)
3. `GET /api/history` → both runs listed newest-first with timestamp/profile/params/status; open one → full results as captured. (FR-022, FR-023)
- **Pass**: `SC-005`, `SC-006`; history loads < 3 s at scale (`SC-012`).

### US5 — Scheduled jobs (P2)
1. `PUT /api/profiles/{id}/schedule` with a near-future recurrence → `next_run_at` shown. (FR-028, FR-029)
2. Let it trigger (or invoke the scheduler tick) → a DiscoveryRun appears in history with `trigger=scheduled`. (FR-030)
3. Trigger a schedule while a run is in progress → no duplicate; `overlap_policy` applied. (FR-031, FR-043)
4. Stop the app over a due time, restart → `catch_up_policy` applied predictably. (FR-032)
- **Pass**: `SC-007` (triggers on time, zero duplicate concurrent runs).

### US6 — Compliance auditing (P2)
1. On the VoIP profile run, inspect results `findings`:
   - **version_validity**: each asset `compliant | non_compliant | unknown`; verify the check made **zero network calls** (e.g., run with external egress blocked / packet capture shows none). (FR-034, FR-035, SC-009)
   - A firmware version not present in `version_validity.yaml` → `unknown`. (FR-035)
2. **default_credentials** against a SIP target:
   - A target still on default creds → response body matches success keywords → `non_compliant` ("default credentials in use"). (FR-036a, FR-039)
   - A hardened target → no keyword match within the cap → `compliant`. 
   - Verify from the audit log that `attempts_made ≤ 3` and consecutive attempts are ≥ 5 s apart; when the cap is hit without a conclusive match → `inconclusive`. (FR-037, FR-038, SC-008)
   - Confirm no attempted secret is stored/returned anywhere. (FR-039)
- **Pass**: `SC-008`, `SC-009`, `SC-010`, `SC-011`.

---

## Key invariants to assert in CI

- **Auth gate** closes 100% of non-login paths when unauthenticated (US1).
- **Password policy** rejects < 20 chars at create and change (US1).
- **Credential-check guardrails**: attempt count ≤ 3 and inter-attempt spacing ≥ 5 s — enforced centrally and unit-tested as invariants, verifiable in audit log (US6).
- **Offline version check**: zero network I/O during version validity evaluation (US6).
- **No duplicate concurrent runs** per profile across manual + scheduled triggers (US5).
- **Optimistic concurrency**: stale `version_token` on profile save → `409`, no silent overwrite (US2).

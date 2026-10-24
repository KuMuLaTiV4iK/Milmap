# Quickstart & Validation: Credential-Check Tool Fixes

Runnable scenarios that prove the feature works end-to-end. Details live in
[spec.md](./spec.md), [data-model.md](./data-model.md), and
[contracts/http-api-delta.md](./contracts/http-api-delta.md).

## Prerequisites

- Project venv active (Python 3.12), dependencies installed (offline wheelhouse).
- Windows PowerShell (project default shell).

## Setup

```powershell
# 1. Apply schema (fresh DB) + additive columns (existing DB)
python -m asset_dashboard.db.init          # includes _add_missing_columns (this feature)

# 2. Seed reference data (version + default-credential dictionaries + NSE allow-list)
python -m asset_dashboard.db.seed_reference

# 3. Ensure an admin/operator account exists (see project README/quickstart)
#    then run the app:
uvicorn asset_dashboard.main:app --reload
```

A tiny HTTP form-login test server is useful for US3/SC-003. Any server that
serves `GET /` (login page) and `POST /login` returning `200` on correct creds
and `401` otherwise works; point the probe's `probe_config.login_path` at
`/login`.

## Scenario A — once/interval scheduling parity (US1, SC-001/002)

1. Open `/tools/credential-check`. In the schedule form choose **Одноразово**
   (once), set a **future** date/time, a target, port, service, dictionary; save.
2. **Expect**: the task appears with an **Enabled** column and a **Next check
   time** column; the recurrence reads as one-time, not an interval.
3. Edit the task → **Expect**: the form re-opens on "once" with the same
   date/time (no once→interval flip).
4. Create a once task with a **past** time → **Expect**: `422`, field error on
   `recurrence` ("run_at must be in the future").
5. Create an **interval** task (every N hours) → **Expect**: next-run computed N
   hours out; table shows interval + next-run.

## Scenario B — choose a dictionary (US2, FR-104)

1. Create two dictionaries for `http` with different vendors/credentials.
2. In the run form select service `http` → **Expect**: the dictionary selector
   lists both; switching service refreshes the list.
3. Delete all `http` dictionaries, try to run `http` → **Expect**: a message to
   create a dictionary first (`422`).

## Scenario C — form-aware HTTP/HTTPS probe (US3, SC-003)

1. Point an `http` dictionary's `probe_config` at the test server
   (`login_path:"/login"`, fields `username`/`password`, `success.status:[200]`,
   `failure.status:[401]`). Put the server's correct creds as one entry and a
   wrong pair as another.
2. Run the check against the server.
3. **Expect (server log)**: a `GET /` (fingerprint) then `POST /login` per
   attempt — **not** repeated `GET /`. Wrong creds → `401` (rejected), correct
   creds → `200` (accepted).
4. Repeat with an `https` target using a **self-signed** cert → **Expect**: the
   probe completes (TLS not rejected) and judges creds the same way.

## Scenario D — exhaustive attempts, cooldown, stop-on-match (US4, SC-004)

1. Build a dictionary of N credentials where the k-th (k<N) is valid; run with
   default ceiling.
2. **Expect**: exactly **k** attempts (stops at the match); consecutive attempts
   ≥5s apart (verify via timestamps/audit; unit tests use an injected
   `sleep_fn`). Result = `non_compliant`.
3. Run against a target where **none** match → **Expect**: all N tried, result
   `compliant` (not `inconclusive`).
4. Set `attempt_ceiling = k-1` (below dict size), no match within it → **Expect**:
   result `inconclusive`.

## Scenario E — live running status (US5, SC-005)

1. Start a run over several targets (so it takes >1 poll interval).
2. **Expect**: it appears in history as `running` immediately (before it
   finishes); history/result view transitions to `completed` via polling without
   a manual refresh.
3. Force a worker error (e.g. unreachable target config) → **Expect**: run ends
   `failed` with an `error_detail`, never stuck `running` (FR-117).

## Scenario F — result window (US6, SC-006)

1. Open a finished run's result page `/tools/credential-check/runs/{id}`.
2. **Expect**: a scan-style table of attempts per target (target, **username**,
   response status/excerpt, result) with the matching row **highlighted** and
   labelled by username + dictionary entry.
3. **Expect (security)**: no password text anywhere in the page, the run-detail
   JSON, or the audit log — search the response for the known secret and confirm
   it is absent (FR-114).

## Scenario G — layout polish (US7, SC-007)

1. Run-now card → **Expect**: target on row 1; port + service + dictionary +
   start button share row 2.
2. Dictionary form → **Expect**: the description/vendor field spans full width.

## Automated test entry points

- `tests/contract/test_credential_tool.py` — dictionary CRUD + `probe_config`
  validation, dictionary selection, async run returns `running`, run-detail
  per-attempt shape, **no secret in any response**.
- `tests/unit/test_credential_guardrails.py` — **updated**: configurable ceiling
  (default = dict size), stop-on-match, ≥5s cooldown still enforced (injected
  `sleep_fn`), `inconclusive` only when a ceiling < dict size is hit.
- `tests/unit/test_http_form_probe.py` — **new**: GET-fingerprint → POST-login →
  status/body validation; self-signed TLS tolerated; excerpt is secret-free.
- `tests/integration/test_us5_credential_tool.py` — background run lifecycle
  (`running` → `completed`/`failed`) and polling-visible status.

## Constitution re-check (post-design)

Principle III is satisfied under the **v2.0.0** amendment: central guard, ≥5s
cooldown non-negotiable, operator-configurable ceiling (default = dict size),
stop-on-match, `inconclusive` on a sub-dictionary ceiling. All other principles
unchanged (see plan.md Constitution Check). Guardrail tests must assert the
cooldown and the ceiling to keep SC-008/002 SC-006 observable.

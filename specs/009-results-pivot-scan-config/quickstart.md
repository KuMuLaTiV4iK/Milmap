# Quickstart & Validation: Scan-Result Host Pivot & Run Configuration Window

Run guide to prove the feature end-to-end. Details live in
[contracts/http-api-delta.md](./contracts/http-api-delta.md) and
[data-model.md](./data-model.md); this file is the validation script, not the
implementation.

## Prerequisites

- Project venv active (Python 3.12); app installed (`pip install -e .`).
- Local SQLite DB initialized; at least one operator account; signed in.
- `nmap` available locally (discovery runs); an air-gapped/offline environment is
  fine.
- A couple of discovery profiles exist, including **one target-less** profile and
  one with a saved target, plus at least one completed run that was evaluated for
  **version validity** and contains a mix of `compliant`, `non_compliant`, and
  `unknown` hosts.

## Run the app

```powershell
# from repo root
uvicorn asset_dashboard.main:app --reload
# open http://127.0.0.1:8000
```

## Automated checks

```powershell
pytest tests/unit/test_invalid_version_select.py `
       tests/contract/test_run_launch_overrides.py `
       tests/integration/test_results_pivot.py
# Plus the existing invariant suite must stay green:
pytest tests/
```

## Scenario A — Scan Configuration page replaces the prompt (US1)

1. On the home dashboard, click **Run now** for the **target-less** profile.
   - **Expect**: navigation to `/profiles/{id}/scan` (a page, not a browser
     prompt). Target field empty; **Start Scan** disabled; a command preview shows.
2. Enter a valid target (e.g. `10.20.0.0/29`), change timing to `T4`, drop a port.
   - **Expect**: preview updates; **Start Scan** enabled.
3. Click **Start Scan**.
   - **Expect**: redirect to `/runs/{run_id}`; the run’s parameters reflect your
     edits.
4. Re-open the profile in the editor.
   - **Expect (SC-004)**: the saved profile’s target/timing/ports are **unchanged**.
5. Click **Run now** on the **targeted** profile, then **Start Scan** without edits.
   - **Expect**: launches (cache may serve a fresh-enough prior run); **no browser
     prompt appears anywhere** (SC-005).

## Scenario B — Credential-check pivot (US2)

1. Open a completed run’s results page (`/runs/{id}`).
2. Tick 2–3 host checkboxes.
   - **Expect**: selection count shows; **Check credentials on selected** enabled
     (it is disabled with 0 selected).
3. Click **Check credentials on selected**.
   - **Expect**: navigation to `/tools/credential-check?targets=…` with exactly
     those addresses pre-filled in the Run-now target field (SC-002 — nothing
     typed).
4. Choose a port, service, and dictionary; click **Run now**.
   - **Expect**: the check runs under the ≥5s cooldown and the attempt ceiling, and
     appears in the credential-tool history and the audit log (SC-006, FR-007/009).

## Scenario C — Scan pivot into a chosen profile (US3)

1. On the same results page, tick a few hosts.
2. Choose **Scan selected with profile…** and pick a *different* profile.
   - **Expect**: navigation to `/profiles/{id}/scan?targets=…` with those hosts
     pre-filled as the target and the chosen profile’s other settings shown.
3. Optionally add/remove a host, then **Start Scan**.
   - **Expect (SC-001)**: a new run targeting exactly the shown hosts, reached in
     ≤3 actions (select → choose profile → Start Scan), under 30s, no retyping; the
     chosen profile’s saved target is unchanged (SC-004).
4. Immediately try to launch the same profile again while it runs.
   - **Expect**: `409 already_running` surfaced as a clear message (FR-019).

## Scenario D — Auto-select invalid-version hosts (US4)

1. On a results page evaluated for version validity, note which hosts are
   `non_compliant`, `unknown`, and `compliant`.
2. Manually tick one `compliant` host, then click **Select invalid-version hosts**.
   - **Expect**: all `non_compliant` rows become selected **in addition to** your
     manual tick (union, Q1); **no** `unknown` or `compliant` row is auto-selected
     (SC-003).
3. Open a run that was **not** evaluated for version validity.
   - **Expect**: **Select invalid-version hosts** is disabled with a short reason
     (FR-004); manual checkboxes still work.

## Negative / edge checks

- Enter an invalid target (`10.0.0.999`) or bad port (`abc`) on the scan page →
  inline field error, no run starts.
- `POST /api/profiles/{id}/runs` with `scan_params: {"script":"x"}` →
  `400 validation_error` (disallowed key; FR-018).
- Clear the target field on the scan page → **Start Scan** disabled; forcing an
  empty-target request still returns `400 target_required` (SC-007).
- Select 100+ hosts → single valid pre-filled target list on the destination page.

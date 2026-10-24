# Quickstart & Validation: Home Page & Results Corrections

Validation guide for feature 003. Proves each user story end-to-end. Assumes the
existing air-gapped dev setup from features 001/002.

## Prerequisites

- Python venv active; dev deps installed (`pip install -e ".[dev]"`).
- Apply migrations: `alembic upgrade head` (brings in migration `0003`:
  `schedules.target_scope`, `schedules.label`, drop `UNIQUE(profile_id)`).
- A signed-in session (first account is Administrator; create an Operator too to
  check reference-versions editing works for both roles).
- `nmap` on PATH for live runs; parser/unit tests use canned XML fixtures and
  need no binary. Sample fixture: `1_prof_output.txt` (2 ports: 192.168.1.1 has
  22 open, 8291 filtered).

## Run the app

```powershell
uvicorn asset_dashboard.main:app --reload
# open http://127.0.0.1:8000/
```

## Automated checks

```powershell
pytest                 # full suite — existing 001/002 tests must stay green (SC-008)
pytest tests/unit      # port-state persistence + size rendering, open-port version,
                       # target-optional validation, schedule-target validation, tick w/ target
pytest tests/integration -k "us1 or us2 or us3 or us4 or us5 or us6"
pytest tests/contract -k "schedule or reference_versions or runs or profiles"
ruff check . ; black --check .
```

## US1 — Home page & target-less launch

1. Create at least one profile with **no** `version_validity` and run it once.
2. Open `/` → heading and nav read **"Головна"**; the page is **not** empty.
   - Expect ≤5 recent profiles (most-recent first), each with a **Run now**
     action; expect the recent-scans overview listing that non-compliance scan
     (SC-001, SC-002a, FR-001/002/004/005). A scan with no version evaluation
     shows compliance "not applicable", not hidden.
3. Click **Run now** on a recent profile → a run starts and you land on its
   detail view (SC-002).
4. Create a profile with an **empty target**; save succeeds (FR-003a). Launch it
   from Home **and** from the profiles list → each prompts for a target; supplying
   one starts a run with that target and the profile's unchanged ports (FR-003b).
   Reopen the profile → still target-less (FR-003c).
5. Supply an invalid target at launch → rejected, no run starts (FR-003d).

## US2 — Dynamic UI

1. On `/profiles`, **duplicate** a profile → the copy appears without a manual
   reload (FR-007). **Delete** a profile → its row disappears without reload.
2. Create/edit a profile → the list reflects it on return (FR-006).
3. Force a failing mutation (e.g. delete something already removed in another
   tab) → the view stays consistent with the server and an error is shown, not a
   silently wrong list (FR-008).

## US3 — Ports column

1. **Small scan** against `1_prof_output.txt` (2 ports): 192.168.1.1's row shows
   `22/tcp open` **and** `8291/tcp filtered` with their states (FR-009, SC-004).
2. **Large scan** (>10 ports): each host's row lists only **open** ports;
   filtered/closed are omitted and never shown as open (FR-009a/FR-009b).
3. Large scan, responding host with no open ports → the row shows
   **"Всі порти closed або filtered"** and the host still appears (FR-010).
4. Service version shown comes from an **open** port (FR-011).

## US4 — Non-compliant remediation + reference view

1. Ensure the reference dataset lists OpenSSH `7.*` invalid and `9.*` valid.
   Scan a host detecting OpenSSH 7.4.
2. Its results row is **orange-highlighted**, shows `non_compliant`, and surfaces
   the expected valid version / note (e.g. "upgrade to 9.x") (FR-012/FR-013,
   SC-005). Compliant/unknown rows are not orange (FR-014).
3. Open `/reference-versions` → the maintained list is visible (vendor, product,
   version match, status, note) (FR-015, SC-006).
4. As an **Operator** and as an **Administrator**, add/edit/remove an entry → the
   change takes effect for the next evaluation and appears in the audit log as a
   `CONFIG_CHANGE` (FR-015a/FR-015b).

## US5 — NSE scripts list control

1. Open the profile editor → allow-listed NSE scripts are offered through a
   list/drop-down control (FR-016).
2. Select one or more, save, reopen → exactly those stay selected and appear in
   the command preview (FR-017, SC-007). A since-disabled script fails save
   validation as before.

## US6 — Schedule profile scans

1. From a profile (or the schedules page), create a recurring schedule, supplying
   the schedule's **own target** and a recurrence → it saves without editing the
   profile (FR-020/FR-021). Create a **second** schedule for the same profile with
   a different target → both are honored (multiple per profile).
2. Let a schedule fire (use a short interval, or call `tick()` in a test) → the
   profile's scan runs against the schedule's target, is stored in history and
   the audit log like a manual run (FR-022, SC-009).
3. Change the profile's saved target → existing schedules keep their own target.
4. From `/history`, pick a past scan and choose **schedule this scan** → a
   recurring schedule is created reusing that run's profile and target (FR-023,
   SC-011).
5. Try to create a schedule with an empty/invalid target → rejected (FR-021b).
6. A scheduled run that would duplicate an in-progress run of the same profile is
   suppressed by the existing overlap handling (edge case).

## Constitution re-check (post-design)

- No new runtime dependency added (Principle I).
- Credential tool/device-safety guard untouched (Principle III).
- Launch-time and per-schedule targets reuse `validate_target_scope`; no
  free-form nmap flags (Principle II).
- Reference-version edits, schedule changes, and runs are audit-logged
  (Principle IV).
- Existing invariant suite stays green (Principle V; SC-008).

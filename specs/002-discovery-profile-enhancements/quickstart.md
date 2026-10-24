# Quickstart & Validation Guide: Feature 002

How to run Milmap with the feature-002 changes and validate each user story end-to-end. This is a run/validation guide; implementation details live in `data-model.md`, `contracts/http-api-delta.md`, and (after `/speckit-tasks`) `tasks.md`.

## Prerequisites

- Python 3.15 environment from the repo `.venv`; dependencies already vendored (no internet). No new packages are added by this feature.
- System `nmap` on PATH, with its local NSE script store installed (for `--script`). For the MikroTik example, a reachable device on port 8291 is needed to see a real version string; absence just yields an empty result (no error).
- A test target or subnet you are authorized to scan.

## Setup

```powershell
# From repo root
.\.venv\Scripts\activate
# Apply migrations (adds role, selected_scripts, NSE allow-list, settings, tool tables)
alembic upgrade head
# Seed reference data incl. the default NSE allow-list
python -m asset_dashboard.db.seed_reference
# Create the FIRST account -> becomes Administrator automatically
python -m asset_dashboard.auth.create_account --username admin
# Run the app
uvicorn asset_dashboard.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/` in a local browser. Confirm the page is branded **Milmap**, dark SOC theme, Ukrainian labels.

## Validation by user story

### US1 — Edit an existing profile (FR-002, FR-003)

1. Create a profile, return to `/profiles`.
2. Confirm each row shows an **Edit** button; click it → editor opens pre-filled.
3. Change the name and save → same profile updated in place, no duplicate in the list.
4. Simulate a stale edit (change `version_token`) → save rejected with a conflict message (409), stored profile unchanged.

### US2 — Full control over the scan command (FR-001, FR-005–FR-009)

1. In the editor for a **new** profile, confirm the timing template is pre-selected to **T3**.
2. Confirm "Extract open ports" and "Extract service/firmware version" are **enabled, independent** checkboxes (not greyed/forced).
3. Save an **open-ports-only** profile (version extraction off) → saves successfully.
4. Use the **effective-command preview**; confirm it matches your selections exactly and that `-sV` appears only when version extraction is on.
5. Run both variants; confirm the version-off run reports no version data without error.

### US3 — Configuration: account, roles, users (FR-026–FR-034)

1. As `admin`, open `/configuration`; change your own password (try < 20 chars → rejected).
2. Create a second user with role **Operator**; sign in as them.
3. As the operator, confirm you can create/run profiles and use tools, but `/configuration` shows **no** user-management, security-settings, or allow-list sections, and direct API calls to those return **403**.
4. As admin, try to set `password_min_length` to 10 → rejected (floor 20). Set session idle timeout; confirm it takes effect.
5. As admin, try to deactivate/demote the only administrator → rejected (`last_admin`). Deactivate the operator → their session is invalidated and sign-in denied.
6. Confirm every action above appears in the audit log.

### US4 — NSE scripts + allow-list (FR-010–FR-018)

1. As admin in `/configuration`, confirm the allow-list shows `mikrotik-routeros-version` (seeded).
2. Add a new safe script → appears in the profile NSE checklist immediately (no redeploy).
3. Add a non-safe script → a warning is shown but the add succeeds; confirm `ALLOWLIST_CHANGE` audit entries.
4. Select scripts on a profile, run it → confirm the command includes `--script <ids>` and script output appears per host in results.
5. Remove a script from the allow-list that a profile references → that profile can no longer run it (selection flagged/disabled).

### US5 — Standalone credential tool, on demand & scheduled (FR-020–FR-025)

1. Open `/tools/credential-check`; run on demand against a test host (`service=ssh`, a port). Confirm per-target result (compliant/non-compliant/inconclusive) and `attempts_made ≤ 3`.
2. From the audit log / run detail, confirm **no more than 3 attempts** and **≥ 5 s** between attempts (device-safety guard).
3. Create a **scheduled task** (e.g., interval); confirm `next_run_at` is shown; let it fire (or lower the tick interval in a test) → a `ToolCheckRun` is produced equivalent to the on-demand run.
4. Run a **discovery profile** and confirm it does **not** perform the default-credential check (decoupled).

### US6 — Dark SOC UI in Ukrainian with help (FR-035–FR-038)

1. Navigate every screen (login, profiles, editor, results, history, configuration, credential tool); confirm a consistent dark SOC theme, Ukrainian labels, Milmap branding, no light/unstyled screen.
2. Confirm status indicators (running/failed, compliant/non-compliant/inconclusive) are clearly distinguishable on the dark theme.
3. Hover/activate the `?` on configuration controls (e.g., timing `T3`) → Ukrainian help text appears (e.g., "Налаштування швидкості сканування").
4. Confirm technical identifiers (`T3`, `-sV`, ports, script ids) remain in English.

## Automated test entry points

```powershell
pytest tests/unit            # command build w/ --script, extraction independence, T3 default,
                             # allow-list validation, role authz, password-floor, tool-task scheduling
pytest tests/integration     # test_us1_edit .. test_us6_ui_uk_dark
pytest tests/contract        # test_nse, test_users, test_settings, test_credential_tool (+ changed profiles)
```

Expected: all green, including the carried-over 001 device-safety guardrail tests (now exercised through the standalone tool path).

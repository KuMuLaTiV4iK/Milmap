# Quickstart & Validation: UI Layout Refinements

A run/validation guide that proves the feature end-to-end. It assumes the existing Milmap dev setup. Implementation code belongs in `tasks.md` / the implementation phase; this file only shows how to run and verify.

## Prerequisites

- Python env per repo (`.venv`), dependencies installed from the local lockfile (air-gapped).
- A local database with: at least one discovery profile, a few discovery runs (some with compliance evaluation), at least one **enabled** schedule, and both an **administrator** and an **operator** account.
- App runnable the usual way (e.g. `uvicorn asset_dashboard.main:app` or the project's run skill).

## Run

```powershell
# from repo root, with the venv active
uvicorn asset_dashboard.main:app --reload
# then open http://127.0.0.1:8000/ and sign in
```

## Automated checks (preferred)

```powershell
# full suite
python -m pytest

# focused: the areas this feature touches
python -m pytest tests/unit/test_i18n_help_coverage.py -q
python -m pytest -k "dashboard or preview or configuration or history or profiles or schedule" -q
```

New/updated automated tests to add (map to the UI contract):

- **C-API-1** — `POST /api/profiles/preview-command` with `target_scope: []` returns `200` and a `display` containing the placeholder; with a real target, returns the executable command; bad port spec still `422`.
- **C-API-2** — `GET /reference-versions` redirects to `/configuration`.
- **C-API-3 / C-HOME-3** — Home view returns ≤5 enabled schedules ordered by `next_run_at` asc; excludes disabled; empty list renders the empty state.
- **C-HOME-1/5** — rendered `/` HTML has no `dashboard.subtitle` text and none of the three removed scan headers; keeps "Не відповідає".
- **C-PROF-1 / C-HIST-1** — rendered `/profiles` has no "Розклад" header; `/history` has no "З кешу?" header.
- **C-CFG-5/6** — as operator, `/configuration` DOM contains the version-dictionary + own-password cards only; `/api/users`, `/api/settings/security`, `/api/nse-scripts` return 403; `/api/reference-versions` returns 200.

## Manual validation walkthrough

### Home (US1, US2)

1. Sign in; open `/`.
2. ✅ No "Головна" title and no "Останні профілі…" subtitle at the top.
3. ✅ Profiles list on the left, recent scans on the right.
4. ✅ Under the profiles list: up to 5 schedules, soonest `next_run_at` first. Click one → lands on `/schedules`.
5. ✅ Recent scans has no "Відповідає"/"Невідомо"/"Непереконливо" columns; "Не відповідає" still present.
6. Resize the window to phone width → ✅ columns stack, no horizontal scrollbar.
7. (Empty-state) On a fresh DB, each section shows its placeholder with no error.

### Profile editor (US3)

8. Open `/profiles/new` (no target). ✅ The command preview shows a full `nmap` command with a visible target placeholder (not the bare `nmap …`).
9. Type a target → ✅ preview swaps the placeholder for the real target.
10. Paste 20+ comma-separated ports into the ports field → ✅ the whole list is visible (field expands / is resizable); save succeeds (validation still passes).

### Tables (US4)

11. `/profiles` → ✅ no "Розклад" column.
12. `/history` → ✅ no "З кешу?" column.

### Configuration (US5)

13. As **administrator**, open `/configuration`. ✅ Two subtabs: Subtab 1 = Users + Security settings; Subtab 2 = NSE allow-list + Version dictionary.
14. Enter text in a Subtab 1 field, switch to Subtab 2 and back → ✅ the text is still there (no reload).
15. ✅ Top nav no longer has "Довідник версій"; visiting `/reference-versions` redirects to `/configuration`.
16. Sign out; sign in as **operator**, open `/configuration`. ✅ Only own-password + version-dictionary management visible; no users/security/NSE controls.
17. As operator, add/edit/delete a version-dictionary entry → ✅ works (operator-allowed, audit-logged).
18. As operator, attempt an admin API (e.g. `GET /api/users`) → ✅ `403`.

## Done signal

All automated checks green (including `test_i18n_help_coverage` and the role-based access-control invariant) and the manual walkthrough's ✅ items confirmed on desktop and narrow width.

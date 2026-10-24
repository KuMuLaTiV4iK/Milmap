# Implementation Plan: Milmap — Discovery Profile Enhancements, NSE Scripts, Configuration, Roles & Ukrainian SOC UI

**Branch**: `002-discovery-profile-enhancements` | **Date**: 2026-10-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-discovery-profile-enhancements/spec.md`

## Summary

A second iteration on the air-gapped **Milmap** dashboard (feature `001-asset-compliance-dashboard`) that reworks the Asset Discovery Profile experience and adds operator administration. Profiles become fully operator-controlled: an **Edit** button, a `T3` default timing template (changeable), genuinely independent telemetry-extraction toggles, an effective-command preview, and selectable **NSE scripts** drawn from an admin-curated, UI-editable allow-list. The per-result **host-management link is removed** from profiles and the UI (deferred to a later standalone function). The default-credential check is **decoupled from discovery runs** into a standalone tool that runs on demand or on its own schedule (via the existing shared scheduling engine). A new **Configuration** area introduces two roles (**Administrator**, **Operator**), admin-managed users with a first-account-is-admin bootstrap, admin-editable account/session security settings (≥ 20-char floor preserved), and the NSE allow-list editor. The whole UI is restyled as a dark **SOC** theme, localized to **Ukrainian**, with a `?` help annotation on every configuration control (technical identifiers stay English).

**Technical approach**: Extend the existing single-process FastAPI + Jinja2/HTMX + SQLAlchemy/SQLite + APScheduler application in place — no new runtime dependencies, preserving offline installability. New ORM models (role column, NSE allow-list, DB-backed security settings, tool task + tool-check run) are added via Alembic migrations. `build_nmap_command`/profile validation gain `--script` allow-list support and honor independent extraction flags. The profile editor template is corrected (real checkboxes, T3 default, host-link field removed, NSE checklist, command preview). The scheduler `tick()` is generalized to also dispatch tool tasks. The central `check_default_credentials` guard is reused unchanged by the standalone tool. A thin single-locale Ukrainian string catalog + help-text registry feeds the templates, and `base.css` is reworked to a dark SOC palette.

## Technical Context

**Language/Version**: Python 3.15 (existing `.venv`; `uv`/`uvx` available) — unchanged from feature 001.

**Primary Dependencies** (all already vendored for 001; **no new packages**):
- Web: FastAPI, Uvicorn, Jinja2 (server-rendered), vendored HTMX (`web/static/htmx.min.js`)
- Persistence: SQLAlchemy 2.x + SQLite; Alembic migrations (`migrations/`)
- Scheduling: APScheduler heartbeat calling the in-DB `tick()` (`scheduling/engine.py`)
- Auth: argon2-cffi (Argon2id); server-side sessions + CSRF
- Discovery: system `nmap` via `subprocess`, XML parse (`discovery/parser.py`)
- Credential probes: existing `compliance/probes/{sip,ssh,http,telnet}.py`
- Validation/config: Pydantic v2 (`config.py`)
- Testing: pytest, pytest-asyncio, httpx test client

**Storage**: SQLite under `data/app.sqlite3`. New tables: NSE allow-list, DB-backed security settings, tool tasks, tool-check runs/results; a `role` column on `operator_accounts`; a `selected_scripts` column on `discovery_profiles`. NSE allow-list is seeded from a versioned local file under `data/reference/` (like the existing reference catalogs).

**Testing**: pytest unit (nmap command build incl. `--script`, extraction-flag independence, timing default, allow-list validation, role authz, security-settings floor, tool-task scheduling) + integration (per user story: edit, command control, Configuration/roles, NSE select, standalone credential tool on-demand & scheduled, dark/Ukrainian UI smoke) + contract (new/changed HTTP endpoints). The device-safety guardrail tests from 001 continue to cover the reused credential guard.

**Target Platform**: Single host (Windows 11 confirmed; Linux supported) on an isolated/air-gapped segment; accessed via local browser.

**Project Type**: Web application (single ASGI deployable serving a server-rendered UI).

**Performance Goals**: No scan-performance target in this feature (default `T3`, operator-changeable). Interactive UI parity with 001 (history/list views load < 3 s at ~5,000-host scale).

**Constraints**:
- **Air-gapped**: no new external dependencies; NSE scripts execute only from the local `nmap` install (no `--script-updatedb`, no remote fetch); allow-list and settings stored locally.
- **Device safety (NON-NEGOTIABLE)**: the standalone credential tool reuses the central 3-attempt / ≥ 5-second-cooldown guard unchanged; scheduled runs inherit it.
- **Security**: role-gated admin functions; ≥ 20-char password floor cannot be lowered via Configuration; `nmap` command still composed only from an allow-list (now including a curated NSE-script allow-list) — no free-form flags/scripts; attempted secrets never persisted.
- **Auditability**: allow-list changes, user-management actions, configuration changes, and credential-tool checks are audit-logged.

**Scale/Scope**: Unchanged (~5,000-host inventory; a few concurrent operators). Two roles only; single Ukrainian locale; one standalone tool (credential check) in scope.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution v1.1.0 (ratified 2026-10-21; amended 2026-10-21 to add Principle VII Least-Privilege Roles and expand Device-Safety/Audit/Input-Safety). Evaluation of this feature:

| Principle | Compliance |
|---|---|
| I. Offline-First / Air-Gapped | No new deps; NSE runs from local `nmap` only (FR-017); allow-list/settings seeded & stored locally; version-validity check untouched. ✅ |
| II. Security by Default | Auth gate unchanged; **roles** added (admin-only user/security/allow-list mgmt); ≥ 20-char floor enforced and un-lowerable (FR-032); `nmap` command still allow-list-only — NSE scripts constrained to the curated allow-list, no free-form `--script` (FR-009, FR-013); secrets still only hashed; attempted secrets never persisted (FR-024). ✅ |
| III. Device-Safety Invariants (NON-NEGOTIABLE) | Standalone credential tool **reuses** `check_default_credentials` — the central 3-attempt/≥5 s guard — for both on-demand and scheduled runs (FR-022); limits unchanged. ✅ |
| IV. Auditability | New audit events for allow-list changes, user management, config changes, and credential-tool checks (FR-014, FR-024, FR-029/031); no secrets in detail. ✅ |
| V. Testable & Independently Deliverable | Each user story maps to independently testable modules; new CI checks for extraction-flag independence, NSE allow-listing, role authz, settings floor, and tool-task scheduling. ✅ |
| VI. Simplicity (YAGNI) | Extends the single process in place; **reuses** the one scheduling engine for tool tasks (FR-021) rather than adding a second scheduler; single Ukrainian locale (no i18n framework); two roles (no granular RBAC). ✅ |

**Security & input-safety note**: FR-016 permits an administrator to add a script outside Nmap's "safe" categories, with a warning. This does **not** weaken Principle II: at scan time the command is still composed only from allow-listed entries (never a free-form string), and adding a non-safe entry is an audited, admin-only, deliberate act. The default allow-list ships safe-category scripts only. Recorded as a design decision in `research.md`, not a violation.

**Gate result**: PASS (no violations; Complexity Tracking empty).

## Project Structure

### Documentation (this feature)

```text
specs/002-discovery-profile-enhancements/
├── plan.md              # This file (/speckit-plan output)
├── spec.md              # Feature specification (+ Clarifications)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (entity deltas)
├── quickstart.md        # Phase 1 output (validation guide)
├── contracts/
│   └── http-api-delta.md # New/changed HTTP endpoints vs feature 001
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

Changes build on the existing `src/asset_dashboard/` tree. New files/dirs marked **[new]**; touched files marked **[mod]**.

```text
src/asset_dashboard/
├── config.py                        # [mod] app name "Milmap"; default_locale="uk"; security-setting defaults
├── db/
│   ├── models.py                    # [mod] +role on OperatorAccount; +selected_scripts on DiscoveryProfile;
│   │                                #       +NseScriptAllowlistEntry, SecuritySetting, ToolTask,
│   │                                #       ToolCheckRun, ToolCheckResult; +AuditEventType members
│   └── seed_reference.py            # [mod] seed default NSE allow-list (incl. mikrotik-routeros-version)
├── auth/
│   ├── authz.py                     # [new] role enum helpers + require_admin / require_operator deps
│   ├── routes.py                    # [mod] change-own-password endpoint; role on session user
│   ├── routes_users.py              # [new] admin user management (CRUD, role, deactivate, reset)
│   └── create_account.py            # [mod] first account => Administrator (bootstrap)
├── profiles/
│   ├── validation.py                # [mod] drop forced MIN_EXTRACTED_FIELDS & host-link check;
│   │                                #       validate selected_scripts against allow-list
│   └── routes.py                    # [mod] accept selected_scripts; honor extracted_fields; drop host_links;
│   │                                #       add effective-command preview endpoint
├── discovery/
│   ├── nmap_runner.py               # [mod] build_nmap_command adds --script from selected_scripts;
│   │                                #       honor independent extraction flags
│   └── runner.py                    # [mod] stop auto-running default-credential check in profile runs;
│   │                                #       stop populating management_link
├── nse/
│   ├── allowlist.py                 # [new] allow-list CRUD + validation + default seed loader
│   └── routes.py                    # [new] admin allow-list API (+ non-safe warning)
├── settings_store/
│   ├── service.py                   # [new] DB-backed security settings (get/update, ≥20 floor)
│   └── routes.py                    # [new] admin security-settings API
├── tools/
│   └── credential_tool/
│       ├── service.py               # [new] on-demand standalone check (reuses check_default_credentials)
│       ├── tasks.py                 # [new] ToolTask run dispatch (called from scheduler tick)
│       └── routes.py                # [new] run-now + task CRUD API + pages
├── scheduling/
│   └── engine.py                    # [mod] tick() also scans ToolTask and dispatches tool runs
├── compliance/
│   └── evaluate.py                  # [mod] remove default-credential path from profile-run evaluation
├── web/
│   ├── i18n.py                      # [new] Ukrainian string catalog + help-text registry + Jinja helpers
│   ├── dashboard.py                 # [mod] nav/branding; Configuration + Tools entry points
│   ├── static/base.css             # [mod] dark SOC theme
│   └── templates/
│       ├── base.html                # [mod] "Milmap" brand, dark theme, Ukrainian nav, role-aware menu
│       ├── profiles_list.html       # [mod] Edit button per profile
│       ├── profile_editor.html      # [mod] real extraction checkboxes, T3 default, NSE checklist,
│       │                            #       command preview, host-link field removed, ? help, Ukrainian
│       ├── configuration.html       # [new] account/password, users, security settings, allow-list
│       ├── credential_tool.html     # [new] standalone credential tool (run-now + schedule)
│       └── *.html                   # [mod] Ukrainian + dark theme across remaining screens
└── main.py                          # [mod] register new routers

data/reference/
└── nse_allowlist.json               # [new] seed default NSE allow-list (safe scripts; mikrotik-routeros-version)

migrations/versions/
└── 0002_*.py                        # [new] Alembic: role, selected_scripts, new tables, audit enum members

tests/
├── unit/                            # [mod/new] command-build w/ --script, extraction independence, timing
│                                    #           default, allow-list validation, role authz, settings floor
├── integration/                     # [new] test_us1_edit, test_us2_command_control, test_us3_configuration,
│                                    #       test_us4_nse, test_us5_credential_tool, test_us6_ui_uk_dark
└── contract/                        # [new] test_nse, test_users, test_settings, test_credential_tool
```

**Structure Decision**: Continue the single-project web application from feature 001, adding cohesive packages (`nse/`, `settings_store/`, `tools/credential_tool/`, `auth/authz.py` + `routes_users.py`) and generalizing the existing scheduler rather than introducing new processes or services. This keeps the deployment a single self-contained, air-gapped unit (Principle VI) and lets each new user story map to an independently testable module (Principle V).

## Complexity Tracking

> No constitution violations to justify. (Section intentionally empty.)

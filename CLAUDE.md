# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project

**Asset Inventory & Compliance Management Dashboard** — an internal, **air-gapped**, local web application used by the organization's own Network Systems Administrators to inventory internal infrastructure and audit its security-compliance posture. This is a **defensive network-administration tool** operated against authorized, internally owned assets.

Core capabilities:

1. **Strict local authentication** — username + password, with a policy enforcing a minimum password length of 20 characters. No external identity provider (air-gapped).
2. **Asset Discovery Profiles** — full CRUD; each profile orchestrates the underlying telemetry tool (**nmap**) to map internal infrastructure, with customizable scan parameters to optimize discovery time, per-profile selection of extracted telemetry fields (open ports, service/firmware versions), and clickable links to internal host-management pages in the results table.
3. **Persistent history & caching** — every discovery run is stored; a dedicated panel shows historical runs; recent results can be served from cache to avoid redundant network load.
4. **Job scheduling engine** — profiles run automatically on a recurring schedule.
5. **Compliance auditing** — version/firmware validity checked **offline** against a locally maintained reference dataset; a guarded default-credential check (max **3 attempts**, **5-second cooldown** between attempts, to avoid locking out devices) flags devices still using factory-default vendor credentials.

## Workflow: Spec Kit

This project uses **GitHub Spec Kit**. The spec-driven flow is:

- `/speckit-constitution` — establish project principles (constitution is still the template; fill before planning if desired).
- `/speckit-specify` — baseline specification. **Done:** `specs/001-asset-compliance-dashboard/spec.md`.
- `/speckit-clarify` — optional, de-risk ambiguities before planning.
- `/speckit-plan` — implementation plan (introduces the actual tech stack).
- `/speckit-tasks` — dependency-ordered task list.
- `/speckit-implement` — execute tasks.

Spec Kit assets live in `.specify/` (templates, scripts, memory/constitution, `feature.json` pointing at the active feature). Commands/skills are in `.claude/skills/speckit-*`.

### Spec conventions

- Keep `spec.md` focused on **WHAT/WHY**, not HOW. `nmap` appears only because the user designated it as the underlying telemetry tool (a domain dependency), not as a dashboard implementation choice. Defer all other tech-stack decisions to `/speckit-plan`.
- Features are numbered sequentially under `specs/NNN-short-name/`.

## Environment

- OS: Windows 11; shell: PowerShell (Spec Kit scripts are under `.specify/scripts/powershell/`).
- Python virtual env in `.venv/` (Python 3.15); `uv`/`uvx` and `specify` CLI available.
- **Air-gapped target environment**: assume no internet access at runtime; all reference data is provisioned/updated locally.

## Security posture

This is legitimate defensive/administrative tooling for authorized internal use. When implementing: never persist credential secrets in recoverable form, honor the default-credential check's attempt/cooldown limits exactly (they protect target devices), store password material only hashed, and record security-relevant events to an audit log.

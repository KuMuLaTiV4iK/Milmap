# Implementation Plan: Asset Inventory & Compliance Management Dashboard

**Branch**: `001-asset-compliance-dashboard` | **Date**: 2026-10-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-asset-compliance-dashboard/spec.md`

## Summary

A local, **air-gapped** web application for Network Systems Administrators to inventory internal infrastructure and audit its compliance posture. Administrators define reusable **Asset Discovery Profiles** that orchestrate `nmap` to map targets, extract telemetry (open ports, service/firmware versions), and link each result to its internal host-management page. Runs are persisted with a history panel and a freshness-window cache to avoid redundant scanning, and can be scheduled to run automatically. Compliance auditing evaluates firmware/version validity **offline** against a local reference dataset and runs a strictly guarded default-credential check (real, rate-limited authentication attempts — max 3, ≥5 s cooldown — confirmed by keyword/signature matching on the response body).

**Technical approach**: A single self-contained Python web application (FastAPI + Uvicorn) that serves a **server-rendered** UI (Jinja2 + vendored HTMX, no Node/CDN build chain so it installs cleanly on an isolated host). Persistence is SQLite via SQLAlchemy (file-based, ideal for a single-host air-gapped deployment at the ~5,000-host scale). Scheduling uses APScheduler in-process. Discovery invokes the system `nmap` binary as a subprocess and parses its XML output. Compliance probes are a pluggable per-protocol set (SIP, SSH, HTTP, Telnet). Passwords are hashed with Argon2id; sessions are server-side with idle timeout and sign-in throttling. All dependencies are vendorable offline (via `uv`/wheels) to satisfy the air-gap constraint.

## Technical Context

**Language/Version**: Python 3.15 (existing `.venv` in repo; `uv`/`uvx` available)

**Primary Dependencies**:
- Web: FastAPI, Uvicorn (ASGI), Jinja2 (server-rendered templates), HTMX (vendored static asset — no CDN)
- Persistence: SQLAlchemy 2.x + SQLite (stdlib `sqlite3` driver); Alembic for schema migrations
- Scheduling: APScheduler (in-process, SQLAlchemy job store for durability across restarts)
- Auth: argon2-cffi (Argon2id password hashing); itsdangerous / server-side session store
- Discovery: system `nmap` binary via `subprocess` + XML parsing (`python-libnmap` or stdlib `xml.etree`)
- Compliance probes: `paramiko` (SSH), `httpx` (HTTP, local-only), `telnetlib3` or raw `asyncio` sockets (Telnet — `telnetlib` was removed in Python 3.13+), raw UDP/TCP sockets (SIP OPTIONS/REGISTER)
- Validation/config: Pydantic v2
- Testing: pytest, pytest-asyncio, httpx test client; `schemathesis` optional for contract tests

**Storage**: SQLite database file under `data/` (profiles, runs, results, findings, schedules, accounts, audit log). Reference datasets (version-validity data, default-credential catalog) stored as locally editable data (SQLite tables seeded from versioned YAML/JSON files under `data/reference/`).

**Testing**: pytest (unit + integration); contract tests against the HTTP API from `contracts/`; probe guardrail tests assert the 3-attempt / 5-second-cooldown invariants.

**Target Platform**: Single host (Windows 11 confirmed; Linux supported) on an isolated/air-gapped network segment. Accessed via a local browser.

**Project Type**: Web application (single deployable: ASGI backend serving a server-rendered UI).

**Performance Goals**: Interactive UI (history panel loads < 3 s per SC-012). A single run covers up to a /22 (~1,024 addresses); discovery wall-clock is bounded primarily by `nmap` timing parameters, not the app. Support ~5,000 hosts of accumulated inventory.

**Constraints**:
- **Air-gapped**: no internet at build-time install or runtime; all packages vendored, all reference data local, no external calls during version-validity checks (FR-034).
- **Device safety**: default-credential check MUST NOT exceed 3 attempts/target and MUST wait ≥5 s between attempts (FR-037); exceeding is a correctness failure.
- **Security**: no page/data without auth (FR-001); password ≥20 chars (FR-002); credentials only hashed (FR-003, FR-039); audit all security-relevant events (FR-006).
- **Concurrency**: a few simultaneous operators with edit-conflict detection and no duplicate concurrent runs (FR-041–FR-043).

**Scale/Scope**: Up to ~5,000 hosts inventory; single run ≤ ~1,024 addresses (/22); a few concurrent operators; v1 excludes automated remediation, SSO/IdP, multi-site federation, internet feeds.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The project constitution (`.specify/memory/constitution.md`) is the **unratified stock template** — it contains placeholder principles only, so there are no ratified gates to evaluate. Planning proceeds applying the following **spec-derived default principles** (recommend ratifying these via `/speckit-constitution`):

| Principle (default) | Plan compliance |
|---|---|
| Offline-only / air-gapped | No CDN/Node; deps vendored; reference data local; version-validity check does zero network I/O. ✅ |
| Security-first | Auth gate, Argon2id, ≥20-char policy, session timeout, sign-in throttle, no plaintext secrets. ✅ |
| Device-safety invariants | Probe engine enforces attempt/cooldown caps centrally; unit-tested as invariants. ✅ |
| Auditability | Central audit log for auth, config changes, runs, compliance checks. ✅ |
| Testability | Each user story independently testable; contract + integration + guardrail tests. ✅ |
| Simplicity (YAGNI) | Single deployable, SQLite, in-process scheduler — no distributed components for this scale. ✅ |

**Gate result**: PASS (no violations; Complexity Tracking left empty).

## Project Structure

### Documentation (this feature)

```text
specs/001-asset-compliance-dashboard/
├── plan.md              # This file (/speckit-plan output)
├── spec.md              # Feature specification (+ Clarifications)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── http-api.md      # HTTP endpoint contracts (UI + JSON)
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
src/asset_dashboard/
├── __init__.py
├── main.py                 # ASGI app factory, Uvicorn entry, startup/shutdown (scheduler)
├── config.py               # Settings (Pydantic): paths, timeouts, freshness window, limits
├── db/
│   ├── base.py             # SQLAlchemy engine/session (SQLite), migrations wiring
│   └── models.py           # ORM models (see data-model.md)
├── auth/
│   ├── passwords.py        # Argon2id hashing + ≥20-char policy
│   ├── sessions.py         # Server-side sessions, idle timeout
│   ├── throttle.py         # Sign-in failure throttling/lockout
│   └── routes.py           # Sign-in / sign-out / account mgmt
├── profiles/
│   ├── service.py          # CRUD + optimistic concurrency (version token)
│   ├── validation.py       # nmap param allow-list + target parsing
│   └── routes.py
├── discovery/
│   ├── nmap_runner.py      # subprocess orchestration + cancellation
│   ├── parser.py           # nmap XML → structured results
│   ├── runner.py           # run lifecycle, concurrency limiter, cache lookup
│   └── routes.py
├── compliance/
│   ├── version_check.py    # OFFLINE validity vs reference dataset
│   ├── credential_check.py # guarded orchestrator (3 attempts / 5 s cooldown)
│   └── probes/             # sip.py, ssh.py, http.py, telnet.py (+ base.py keyword match)
├── history/
│   ├── service.py          # run persistence, retention policy
│   └── cache.py            # freshness-window reuse / force-fresh
├── scheduling/
│   ├── engine.py           # APScheduler setup, overlap + catch-up policy
│   └── routes.py
├── audit/
│   └── log.py              # append security-relevant events
└── web/
    ├── templates/          # Jinja2 (login, dashboard, profiles, results, history, schedules)
    └── static/             # vendored HTMX, CSS (no external fetch)

data/
├── app.sqlite3             # runtime database (gitignored)
└── reference/
    ├── version_validity.yaml   # seedable offline version dataset
    └── default_credentials.yaml# seedable offline credential catalog + success keywords

tests/
├── unit/                   # password policy, param validation, cache, keyword match
├── integration/            # per user-story flows (auth, CRUD, run, history, schedule, compliance)
└── contract/               # HTTP API conformance against contracts/http-api.md
```

**Structure Decision**: Single-project web application. The ASGI backend both exposes a JSON/HTML API and renders the UI (Jinja2 + vendored HTMX), avoiding a separate frontend build toolchain — a deliberate choice for air-gapped installability. Discovery, compliance, history, scheduling, and auth are separated into cohesive packages so each spec user story maps to an independently testable module. Reference datasets and the SQLite DB live under `data/` so the entire offline deployment is self-contained.

## Complexity Tracking

> No constitution violations to justify. (Section intentionally empty.)

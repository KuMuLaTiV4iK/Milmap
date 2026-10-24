# Phase 0 Research: Asset Inventory & Compliance Management Dashboard

**Date**: 2026-10-21 | **Feature**: `001-asset-compliance-dashboard`

This document resolves the open technical decisions behind the plan. No `NEEDS CLARIFICATION` items remain in the spec (the three clarifications were resolved in the Clarifications session). The research below records the technology and approach decisions, their rationale, and rejected alternatives.

## 1. Application architecture & web framework

- **Decision**: Single-deployable ASGI web app using **FastAPI + Uvicorn**, serving a **server-rendered** UI with **Jinja2** templates and **vendored HTMX** for partial-page interactivity. No Node/npm build, no CDN references.
- **Rationale**: Air-gapped hosts cannot pull npm packages or CDN assets at install or runtime. A server-rendered app with one vendored JS file installs from a single wheel set and runs behind one process. FastAPI gives async request handling (useful while long discovery runs execute in the background) and first-class Pydantic validation. The scale (few operators, ~5k hosts) does not justify a SPA.
- **Alternatives considered**:
  - **Flask + templates**: viable and simpler, but no native async; background-run coordination is clumsier.
  - **React/Vue SPA**: requires a Node toolchain and bundling that is painful to vendor and maintain on an isolated host; rejected as over-engineered for this UI.
  - **Django**: batteries-included but heavier than needed; its ORM/admin add surface we don't require.

## 2. Persistence

- **Decision**: **SQLite** (single file under `data/`) accessed via **SQLAlchemy 2.x**, with **Alembic** migrations. WAL mode enabled for better read/write concurrency.
- **Rationale**: Single-host, air-gapped, ~5,000-host inventory with a few concurrent operators is squarely within SQLite's comfort zone. File-based storage means the whole deployment (DB + reference data) is self-contained and trivially backed up. WAL mode handles the handful of concurrent readers/writers.
- **Alternatives considered**:
  - **PostgreSQL**: operationally heavier (separate service, patching) with no benefit at this scale on an isolated box; rejected.
  - **Flat JSON files**: no transactional integrity or query ability for history/caching; rejected.

## 3. Discovery: orchestrating nmap

- **Decision**: Invoke the **system `nmap` binary** as a subprocess, producing XML output (`-oX -`), parsed into structured results via **python-libnmap** (fallback: stdlib `xml.etree`). The app shells out rather than reimplementing scanning.
- **Rationale**: The spec designates `nmap` as the telemetry tool (FR-015). XML is nmap's stable machine-readable contract and captures ports, service/version detection (`-sV`), and host state. Subprocess control gives clean start/cancel (terminate the process group) and lets profile parameters map directly to nmap flags.
- **Scan-parameter allow-list**: Profiles expose a curated, validated set of tunables (timing template `-T0..-T5`, port spec, `-sV` version intensity, host-discovery toggles, `--max-rate`, `--host-timeout`). Raw free-form flags are rejected; only allow-listed options with validated values reach the command line (FR-011) — this both optimizes discovery time and prevents command injection.
- **Privilege note**: Some scans (e.g., SYN scan, OS detection) need elevated privileges; the plan assumes nmap is installed with sufficient privilege (spec Assumption). The runner reports a clear failure if nmap is missing or under-privileged (FR-020).
- **Alternatives considered**:
  - **python-nmap**: thin wrapper, less maintained; libnmap's object model is richer. Either works; libnmap preferred.
  - **Reimplement scanning (scapy/sockets)**: duplicates nmap, loses its fingerprinting; contradicts FR-015; rejected.

## 4. Compliance — offline version/firmware validity

- **Decision**: Version validity is evaluated **entirely offline** against a locally maintained reference dataset (`data/reference/version_validity.yaml`, seeded into a SQLite table). Each discovered service/version is matched (exact + range rules) and flagged **valid / invalid(outdated) / unknown** (FR-034, FR-035). No network or external lookup occurs during the check.
- **Rationale**: Air-gap forbids external CVE/feed lookups; the organization curates the dataset offline (FR-040). "Unknown" is a first-class result so stale reference data is visible rather than silently mis-scored.
- **Dataset shape**: vendor/product → list of {version or version-range, status, note}. Versioned file so updates are reviewable; importable via a UI/admin path.
- **Alternatives considered**: bundling a static CVE database — larger, still offline, but far heavier to maintain and out of scope for v1; rejected in favor of a curated validity list.

## 5. Compliance — guarded default-credential check (real, bounded auth)

- **Decision**: A central **credential-check orchestrator** performs **real** authentication attempts over the device's service protocol, enforcing the guardrails as hard invariants: **≤ 3 attempts per target** and **≥ 5 s cooldown between consecutive attempts** (FR-037). Success is determined by **matching expected keywords/signatures in the response body** per vendor/service from the catalog (FR-036a), not merely a protocol status. On reaching the cap without a conclusive result, the asset is flagged **inconclusive** (FR-038); a keyword match flags **non-compliant ("default credentials in use")** (FR-039). Attempted secrets are never persisted in recoverable form.
- **Guardrail enforcement**: attempt counting + cooldown live in the orchestrator, *not* in individual probes, so every protocol inherits the same safety limits. The limits are covered by dedicated invariant unit tests (asserting attempt count ≤ 3 and inter-attempt gap ≥ 5 s) and are observable in the audit log (SC-008).
- **Per-protocol probes** (pluggable `probes/` with a common `base.py` keyword-match contract):
  - **SIP (VoIP, ports 5060–5062)**: craft SIP `REGISTER`/`OPTIONS` over UDP/TCP with raw sockets; inspect response body for success/auth-failure signatures. Primary target of the "VoIP Infrastructure Audit" example.
  - **SSH**: **paramiko** auth attempt; success/keyword inspection of banner/post-auth channel output.
  - **HTTP(S)**: **httpx** against the device's local management endpoint (local addresses only); keyword match on response body. No external hosts.
  - **Telnet**: Python 3.13+ **removed `telnetlib`**, so use **telnetlib3** (async) or a minimal raw-socket Telnet exchange; keyword match on the post-login banner/prompt.
- **Rationale**: Clarification selected Option A (real bounded attempts) with response-body keyword confirmation. Centralizing guardrails guarantees the device-safety invariant regardless of protocol. Raw sockets for SIP avoid a heavy VoIP dependency and keep the probe auditable.
- **Alternatives considered**:
  - **Offline inference only** (Option B) — rejected per clarification.
  - **Per-probe attempt counting** — rejected: risks drift/omission of the safety cap; must be central.
  - **pysip/third-party SIP stack** — heavier than needed for a REGISTER/OPTIONS probe; raw sockets preferred for transparency.

## 6. Job scheduling

- **Decision**: **APScheduler** in-process, with a **SQLAlchemy job store** (durable across restarts). Recurrence via cron/interval triggers. The engine enforces **overlap policy** (skip or queue — default skip) and **catch-up policy** (default: run-once-on-startup if missed, configurable) (FR-028–FR-032).
- **Rationale**: In-process scheduler matches a single-deployable design; the SQLAlchemy job store survives restarts so schedules and missed-run handling are predictable (FR-032). No external broker needed at this scale.
- **Alternatives considered**:
  - **Celery + broker (Redis/RabbitMQ)**: distributed task queue, extra services to vendor and operate; over-engineered for one host; rejected.
  - **OS cron / Task Scheduler**: external to the app, can't share concurrency state to prevent duplicate runs (FR-043); rejected as the primary engine.

## 7. Concurrency & conflict handling

- **Decision**: **Optimistic concurrency** on profiles via a per-row version token; a save against a stale version is rejected for reconciliation (FR-042, no silent overwrite). A **run registry** (keyed by profile) plus a bounded **concurrency limiter** prevents duplicate concurrent runs of the same profile and caps total simultaneous runs to protect host/network (FR-021, FR-043).
- **Rationale**: A few concurrent operators (clarified scale) need conflict detection, not heavyweight locking. Optimistic versioning is simple, correct, and testable.
- **Alternatives considered**: pessimistic row locks — unnecessary contention for this usage; last-write-wins — rejected by clarification.

## 8. Authentication & session security

- **Decision**: Local accounts only (no IdP). Passwords hashed with **Argon2id** (argon2-cffi). Policy enforces **≥ 20 characters** at creation and change (FR-002). **Server-side sessions** with configurable **idle timeout** (FR-005) and explicit sign-out. **Sign-in throttling/lockout** after a configurable number of consecutive failures (FR-004). All auth events audited (FR-006).
- **Rationale**: Air-gap rules out SSO; Argon2id is the current best-practice memory-hard hash. Server-side sessions keep revocation and idle-timeout simple. Throttling resists brute force without external dependencies.
- **Alternatives considered**: bcrypt (acceptable fallback, chosen Argon2id as stronger default); stateless JWT (complicates revocation/idle timeout for a server-rendered app) — rejected.

## 9. Caching of discovery results

- **Decision**: A **freshness-window cache**: a request to run a profile/scope reuses the most recent completed run within a configurable window, clearly labelled as cached with its original timestamp; **force-fresh** bypasses and refreshes it (FR-024, FR-025). Cache is derived from persisted runs (no separate store).
- **Rationale**: Avoids redundant network load (a stated goal) while keeping a single source of truth (the run history). Deriving cache from history avoids consistency drift.
- **Alternatives considered**: a separate cache layer (e.g., Redis) — extra service, needless at this scale; rejected.

## 10. Host-management result links

- **Decision**: Per-profile **URL templates** with host placeholders (e.g., `https://{host}/manage`) rendered as clickable links in the results table; rows without a resolvable/configured page render the link as unavailable rather than broken (FR-013, FR-019).
- **Rationale**: Templating keeps the app decoupled from the (externally owned) management pages while giving one-click pivot from finding to action (SC-004).

## 11. Offline dependency provisioning

- **Decision**: Pin dependencies and vendor them as wheels using **`uv`** (already present). Install into the existing `.venv` from a local wheelhouse; HTMX/CSS committed as static assets. Reference datasets ship as seed files.
- **Rationale**: Guarantees reproducible install on an isolated host with no internet (core air-gap constraint).
- **Alternatives considered**: pip + requirements.txt (works; `uv` is faster and already available); conda (heavier) — rejected.

## Summary of key decisions

| Area | Decision |
|---|---|
| Framework | FastAPI + Uvicorn, Jinja2 + vendored HTMX (server-rendered) |
| Storage | SQLite + SQLAlchemy 2.x + Alembic (WAL) |
| Discovery | system `nmap` subprocess, XML parsed via libnmap; validated param allow-list |
| Version validity | fully offline vs curated local dataset; valid/invalid/unknown |
| Credential check | central guarded orchestrator (≤3 attempts, ≥5 s), per-protocol probes (SIP/SSH/HTTP/Telnet), response-body keyword match |
| Scheduling | APScheduler in-process, SQLAlchemy job store, overlap+catch-up policies |
| Concurrency | optimistic profile versioning + run registry/limiter |
| Auth | local accounts, Argon2id, ≥20-char policy, server-side sessions, throttling |
| Caching | freshness-window reuse derived from run history + force-fresh |
| Offline provisioning | `uv` wheelhouse, vendored static assets, seed datasets |

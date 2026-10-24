# Implementation Plan: Version Dictionary Overhaul

**Branch**: `007-version-dictionary-overhaul` | **Date**: 2026-10-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/007-version-dictionary-overhaul/spec.md`

## Summary

V0.7 replaces the version dictionary's **enumerated** model (rows of `product + version_match + valid/invalid`) with a **minimum-version threshold** model: each product/model carries a single *current/actual* version, and compliance is derived by comparison — detected version **below** the threshold → non-compliant, **at/above** → compliant, **no threshold on file** → unknown. A deterministic SemVer-style comparator (clarified) decides ordering; unorderable/mixed-scheme versions → unknown.

It also adds **automated version ingestion**, reconciled with the NON-NEGOTIABLE air-gap as **Option A**: a *separate, standalone fetcher script* runs on an internet-connected staging machine (never inside the deployment), fetches current versions for **one vendor and its models** from the vendor's official source, and emits a **signed/integrity-checked update bundle**. An administrator carries that bundle to the air-gapped app and **imports** it in Configuration Subtab 2 — the app verifies the bundle's integrity, shows a review/diff, and on apply creates/updates thresholds. The running app makes **zero** outbound requests.

Finally, verdicts become **immutable history**: each scan already persists a `ComplianceFinding`; V0.7 also freezes the *checked version* (and the threshold in effect) into that finding, and the evaluator reads the threshold only at scan time, so changing a threshold never rewrites past verdicts.

Technical approach: changes are concentrated in `compliance/` (new comparator + rewritten `version_check`/`evaluate`), `reference_versions/` (threshold CRUD + ingestion config + bundle import), the `db` layer (one Alembic migration `0004` adding threshold + source columns/tables and performing the enumerated→threshold data migration), a new **out-of-runtime** `tools/version_fetcher/` CLI, the Configuration Subtab 2 template, and the Ukrainian i18n catalog. No new runtime network dependency.

## Technical Context

**Language/Version**: Python 3.13+ (repo targets 3.13/3.15). Server-rendered Jinja2 + vanilla JS/HTMX; no frontend framework.

**Primary Dependencies**: FastAPI, Starlette/Jinja2 (`web/templating.py`), SQLAlchemy ORM, Alembic (migrations under `migrations/versions/`, current head `0003_schedule_target_and_label`), HTMX (vendored). Single-locale Ukrainian catalog in `web/i18n.py`. The standalone fetcher is a separate CLI and may use a vendored HTTP client (e.g. `httpx`/`requests`) **only in the staging tool**, never imported by the web app.

**Storage**: SQLite via SQLAlchemy under local `data/`. **Schema change in this feature** — new threshold columns on `reference_version_entries`, a new `version_ingestion_sources` table, and the enumerated→threshold data migration, all in Alembic revision `0004_version_dictionary_overhaul` (down_revision `0003_schedule_target_and_label`).

**Testing**: pytest. New/updated suites: version comparator unit tests (ordering, pre-release, missing segments, unorderable), threshold evaluation tests, migration test (lowest-valid derivation + invalid-only → review), bundle integrity verify/reject tests, import review/apply + downgrade-guard tests, role-gating tests (ingestion admin-only; manual edit operator+admin), immutable-history test (change threshold → past findings unchanged), i18n catalog contract.

**Target Platform**: Single-host, air-gapped internal web app; modern evergreen desktop browser.

**Project Type**: Web application (server-rendered), single project tree under `src/asset_dashboard/`, plus an out-of-runtime staging CLI under `tools/`.

**Performance Goals**: Evaluation stays a local SQLite lookup + in-memory compare — no network. Target unchanged (sub-200ms server render at the ~5,000-host scale). Comparator is O(segments); threshold lookup is an indexed query by vendor/product.

**Constraints**: Offline/air-gapped — the running app performs no outbound request; all fetching is isolated to the staging CLI. Imported bundles MUST pass integrity verification before any write. All user-facing strings go through `t()`. Ingestion config + import are `require_admin`; manual threshold edit stays `require_operator`. Secrets/keys for bundle signing are provisioned locally (no PKI/CA, no network).

**Scale/Scope**: ~1 Alembic migration, 2–3 new/rewritten compliance modules, 1 new comparator, reference-versions service+routes extended, 1 new ingestion service + import endpoint, 1 new staging CLI package, Configuration Subtab 2 template, i18n catalog. Modest data volume (hundreds of threshold rows, a handful of ingestion sources).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Impact | Status |
|-----------|--------|--------|
| I. Offline-First / Air-Gapped (NON-NEGOTIABLE) | Version-validity evaluation stays a local SQLite lookup with zero external calls. The vendor-site fetch is **physically separated** into `tools/version_fetcher/`, run on a different internet-connected machine; the web app only imports a local bundle file. No new CDN/network asset in the runtime. The fetcher's HTTP dependency is isolated to `tools/` and never imported by `src/asset_dashboard/`. | ✅ PASS |
| II. Security by Default | Imported bundles cross a trust boundary, so they MUST be integrity/authenticity-verified (HMAC/signature over content) before any threshold write; failed verification rejects with no change. Signing key provisioned locally, never logged. No change to auth/sessions/password policy. | ✅ PASS |
| III. Device-Safety Invariants | Untouched — this feature changes only the version-validity control and its data; the guarded default-credential check and its 3-attempt/5-second caps are not altered. | ✅ PASS (N/A) |
| IV. Auditability | Every manual threshold edit and every bundle import is recorded as `CONFIG_CHANGE` with action + source provenance (no secrets). Immutable history (FR-012a) strengthens auditability: past verdicts are never retroactively rewritten. | ✅ PASS |
| V. Testable & Independently Deliverable | Part 1 (threshold model) ships and is testable without Part 2 (ingestion). Each user story is an independent slice; migration, comparator, and import each have dedicated tests. | ✅ PASS |
| VI. Simplicity (YAGNI) | Reuses the existing `ReferenceVersionEntry` table (add columns, repurpose semantics) rather than a parallel table; reuses `CONFIG_CHANGE` audit events and the existing persisted-finding architecture for immutable history. Bundle integrity uses a pre-shared-key HMAC (no PKI). The fetcher stays a thin, pluggable CLI. | ✅ PASS |
| VII. Least-Privilege Roles | Ingestion config + bundle import are **administrator-only** (`require_admin`), matching the "admin library conf tab" framing and the higher trust of cross-boundary data. Manual threshold editing stays operator+admin (`require_operator`), continuing feature 006 A-004. UI hiding is cosmetic; server-side gating is authoritative. | ✅ PASS |

**Initial gate: PASS.** The air-gap tension is resolved by physical separation (Option A); no violation requires Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/007-version-dictionary-overhaul/
├── plan.md              # This file
├── spec.md              # Feature specification (with Clarifications)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (schema deltas + migration rules)
├── quickstart.md        # Phase 1 output (manual + automated validation)
├── contracts/
│   ├── http-api-delta.md   # reference-versions threshold CRUD + ingestion/import endpoints
│   ├── bundle-format.md     # the update-bundle schema + integrity envelope
│   └── fetcher-cli.md       # the standalone staging fetcher CLI contract
└── checklists/
    └── requirements.md  # From /speckit-specify + /speckit-clarify
```

### Source Code (repository root)

```text
src/asset_dashboard/
├── compliance/
│   ├── version_compare.py        # NEW — deterministic SemVer-style comparator (FR-006)
│   ├── version_check.py          # REWRITE — threshold comparison, not enumerated match
│   └── evaluate.py               # EDIT — freeze checked_version + threshold snapshot into finding (FR-012a)
├── reference_versions/
│   ├── service.py                # EDIT — threshold CRUD (min_version), drop valid/invalid status semantics
│   └── routes.py                 # EDIT — threshold payloads; keep require_operator for manual edit
├── version_ingestion/            # NEW package (in-runtime: config + import only, NO fetching)
│   ├── __init__.py
│   ├── models_helpers.py         # (optional) serialization
│   ├── service.py                # tracked-source CRUD, bundle verify, review-diff, apply
│   ├── bundle.py                 # bundle parse + HMAC/integrity verification (FR-016a)
│   └── routes.py                 # NEW endpoints — require_admin (config + import)
├── db/
│   ├── models.py                 # EDIT — ReferenceVersionEntry(+min_version,+model); NEW VersionIngestionSource
│   └── seed_reference.py         # EDIT — seed threshold-shaped version data
├── web/
│   ├── i18n.py                   # EDIT — new Ukrainian strings (thresholds, ingestion, import review)
│   └── templates/
│       └── configuration.html    # EDIT — Subtab 2: threshold editor + ingestion sources + import panel
│
tools/
└── version_fetcher/              # NEW — OUT-OF-RUNTIME staging CLI (internet-connected machine)
    ├── __init__.py
    ├── fetch.py                  # per-vendor fetch → current versions for one vendor's models
    ├── extractors/               # pluggable per-source extraction (regex/selector config)
    └── bundle_writer.py          # emit the signed/integrity-checked bundle

migrations/versions/
└── 0004_version_dictionary_overhaul.py   # NEW — schema delta + enumerated→threshold data migration

data/reference/
└── version_validity.json         # EDIT/MIGRATE — threshold-shaped seed (per-product min_version)

tests/
├── unit/
│   ├── test_version_compare.py           # NEW
│   ├── test_version_threshold_check.py   # NEW
│   └── test_bundle_integrity.py          # NEW
├── integration/
│   ├── test_reference_threshold_crud.py  # NEW/EDIT
│   ├── test_ingestion_import.py          # NEW (verify/reject, review/apply, downgrade guard, roles)
│   ├── test_migration_0004.py            # NEW (lowest-valid derivation; invalid-only → review)
│   └── test_immutable_history.py         # NEW (threshold change leaves past findings intact)
└── unit/test_i18n_help_coverage.py       # EDIT — catalog contract for new keys
```

**Structure Decision**: Single server-rendered project under `src/asset_dashboard/` (matching features 001–006), with the in-runtime ingestion code limited to **configuration + verified import** under a new `version_ingestion/` package, and the actual internet-touching **fetcher isolated entirely under `tools/version_fetcher/`** so that nothing in the air-gapped runtime imports a network client. Schema and data migration ride a single Alembic revision `0004`.

## Complexity Tracking

> No constitution violations — this section is intentionally empty.

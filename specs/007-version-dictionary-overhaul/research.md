# Phase 0 Research: Version Dictionary Overhaul

All spec `[NEEDS CLARIFICATION]` were resolved in `/speckit-clarify` (see spec Clarifications, Session 2026-10-23). This file records the resulting technical decisions and the alternatives weighed.

## D1. Version comparison semantics

- **Decision**: Deterministic SemVer-style comparator in a new `compliance/version_compare.py`. Split each version on `.`; compare numeric segments left-to-right; missing trailing segments are treated as `0` (`9.0` == `9.0.0`). A pre-release/suffix (anything after a non-numeric boundary, e.g. `-rc1`, `b2`) sorts **below** the same base release (`9.0-rc1` < `9.0`). If either side is not orderable by this rule, or the two use mismatched schemes, the comparator signals "not comparable" and the evaluator returns **unknown** — never a guessed verdict.
- **Rationale**: Matches the clarified answer (Q1 → A) and how firmware/software versioning overwhelmingly behaves; lowest surprise and easy to unit-test at boundaries.
- **Alternatives considered**: (B) ignore suffixes entirely — rejected: would treat `9.0-rc1` as compliant with `9.0`. (C) refuse any suffixed version — rejected: pushes too many real devices into unknown. Full `packaging.version`/PEP 440 — rejected: PEP 440 pre-release ordering is close but the dependency isn't needed and firmware strings aren't PEP 440; a small, explicit, well-tested comparator is clearer and air-gap-trivial.

## D2. Threshold data model (reuse vs. new table)

- **Decision**: Reuse `reference_version_entries`. Add `min_version` (string, the current/actual threshold) and `model` (nullable string). An entry now means "for this vendor/product[/model], the minimum acceptable version is `min_version`." The legacy `version_match`/`status` columns are retained by the migration only as provenance for review; new logic ignores them.
- **Rationale**: One product → one threshold row is the simplest shape (Principle VI). Avoids a parallel table and keeps the existing seed/CRUD/route plumbing.
- **Alternatives considered**: A brand-new `version_thresholds` table — rejected as redundant. Keeping `version_match` and overloading it as the threshold — rejected: `min_version` as its own typed column makes comparison and migration explicit and testable.

## D3. Migration of enumerated → threshold (FR-012)

- **Decision**: In Alembic `0004`, for each `(vendor, product)` group, set `min_version` = the **lowest `valid` version on record** (compared with the D1 comparator; wildcard entries like `9.*` normalize to their lowest concrete floor `9.0`). Collapse the group to a single threshold row. A group with only `invalid` rows (no valid floor) is **not** auto-converted: it is retained/flagged for administrator review (recorded in the migration output and surfaced in the UI as "needs review").
- **Rationale**: Clarified answer (Q4 → A). Preserves each product's effective floor so verdicts don't flip silently (SC-008).
- **Alternatives considered**: "one above highest invalid" (B) — rejected: brittle when valid/invalid ranges are non-adjacent. "Carry forward as unknown" (C) — rejected: every product loses coverage until manually touched.

## D4. Immutable history (FR-012a)

- **Decision**: Keep the existing persisted-finding architecture — `ComplianceFinding.result`/`detail` are written once at scan time and never recomputed. V0.7 additionally stores, in the version-validity finding's `detail`, the **checked version string** and the **threshold value in effect at scan time** (`checked_version`, `threshold`). `evaluate_asset_compliance` reads the threshold only during the scan; nothing rewrites prior findings when a threshold later changes.
- **Rationale**: The DB already freezes verdicts; this makes the *inputs* to each verdict self-contained and auditable, satisfying the clarified immutability requirement with minimal change.
- **Alternatives considered**: Recompute historical rows against current thresholds for display — explicitly rejected by the clarification (would mutate history). A separate snapshot table — rejected: the finding's JSON `detail` already carries per-finding context.

## D5. Air-gap reconciliation for ingestion (FR-019, Option A)

- **Decision**: The internet-touching fetch lives in a standalone `tools/version_fetcher/` CLI run on a **separate** internet-connected staging machine. It takes one vendor + its models, fetches current versions from the configured official source, and writes an **update bundle** file. The air-gapped app's `version_ingestion/` package only **imports and verifies** that file — it imports no HTTP client. Enforced structurally (the web app must not import `tools/`), and assertable in a test that scans runtime imports.
- **Rationale**: Only interpretation that honors Principle I without amending the constitution (clarified air-gap context + A-008). The running app never makes an outbound request.
- **Alternatives considered**: Outbound fetch from the deployment via proxy/allow-list (B) — rejected: requires amending the NON-NEGOTIABLE Principle I.

## D6. Bundle integrity / authenticity (FR-016/FR-016a)

- **Decision**: The bundle is a JSON document with a canonicalized `payload` plus an `integrity` envelope: a SHA-256 of the canonical payload and an **HMAC-SHA256** signature computed by the fetcher using a **pre-shared key** provisioned offline on both the staging machine and the deployment. On import, the deployment recomputes the digest and verifies the HMAC before any write; mismatch → reject, no threshold changed. The key is read from local secure config, never logged, never placed in the bundle.
- **Rationale**: Clarified answer (Q2 → A). HMAC with a pre-shared key is air-gap-native (no PKI/CA, no network), simple, and strong enough for an operator-controlled transfer. Detached SHA-256 alone would detect corruption but not authenticity; HMAC adds authenticity cheaply.
- **Alternatives considered**: Asymmetric signatures (ed25519/GPG) — stronger key hygiene but adds key-management/tooling overhead not justified for an internal two-machine transfer; can be a later upgrade. Checksum only — rejected: no authenticity.

## D7. Per-vendor fetch extraction

- **Decision**: The fetcher uses a **pluggable extractor** per source: a small config (CSS selector or regex + a normalization rule) stored with the tracked source, so adding a vendor is data/config, not new runtime code. The CLI ships a couple of built-in example extractors; unknown layouts are handled by the configured selector/regex. A source that is unreachable, times out, or whose extraction yields nothing records a per-model **failure** in the bundle (no fabricated value, FR-017/FR-020).
- **Rationale**: Vendor pages vary; config-driven extraction keeps the staging tool general and the air-gapped app untouched by scraping logic.
- **Alternatives considered**: Hard-coded per-vendor scrapers in the app — rejected (violates D5 separation and Principle VI). A full headless browser — rejected: heavy; most vendor version pages are static HTML/JSON.

## D8. Role gating & audit (FR-014/FR-018, Principle VII)

- **Decision**: `version_ingestion/routes.py` (source CRUD + import/apply) is `require_admin`. `reference_versions/routes.py` (manual threshold CRUD) stays `require_operator`. Both emit `CONFIG_CHANGE` audit events; import events include source/bundle provenance (vendor, source id, bundle digest, counts) and never a secret or key.
- **Rationale**: Clarified answer (Q3 → A) + Principle VII. Reuses existing `require_admin`/`require_operator` dependencies and the `CONFIG_CHANGE` event type — no new audit enum needed.
- **Alternatives considered**: New `VERSION_IMPORT` audit enum — unnecessary; `CONFIG_CHANGE` + `detail.action` is the established pattern (see `reference_versions/routes.py`).

## D9. Schema migration mechanism

- **Decision**: One Alembic revision `0004_version_dictionary_overhaul`, `down_revision = "0003_schedule_target_and_label"` (current head). It adds the threshold columns, the `version_ingestion_sources` table, and runs the D3 data migration in the same upgrade. `db/init.py`'s `create_all` remains for fresh installs; existing deployments upgrade via `alembic upgrade head`.
- **Rationale**: Matches the established migration pattern (features 002/003 under `migrations/versions/`). `create_all` never alters existing tables, so the column additions must be a migration.
- **Alternatives considered**: None — Alembic is the project's committed mechanism.

# Phase 1 Data Model: Version Dictionary Overhaul

Schema deltas against the existing SQLAlchemy models (`src/asset_dashboard/db/models.py`), all delivered in Alembic revision `0004_version_dictionary_overhaul`. Field names are indicative; final types mirror existing conventions (`String`, `Text`, `JSON`, `DateTime`, UUID string PKs, naive-UTC timestamps via `utcnow()`).

## 1. `ReferenceVersionEntry` (MODIFIED) — now a minimum-version threshold

Table `reference_version_entries`. Current columns: `id, vendor, product, version_match, status, note`.

| Column | Change | Notes |
|--------|--------|-------|
| `min_version` | **ADD** `String(128)`, nullable | The current/actual **threshold**. A detected version `< min_version` → non-compliant; `>=` → compliant. Null = no threshold → unknown. |
| `model` | **ADD** `String(128)`, nullable, indexed | Optional product model (populated by ingestion / fine-grained entries). Null = applies at vendor-wide granularity. |
| `type` | **ADD** `String(32)`, nullable, indexed (follow-up to this overhaul; migration `0005_device_type`, replaces `product`) | Physical-device category: `ip_phone \| voip_gateway \| ata \| ucm \| switch \| router`. Pure classification/display — NEVER part of the compliance match key (see Semantics below). |
| `source` | **ADD** `String(16)`, default `"manual"` | Provenance: `manual` or `ingested`. |
| `source_ref` | **ADD** `String(256)`, nullable | For `ingested`: the ingestion source id / vendor URL that set this threshold. |
| `needs_review` | **ADD** boolean, default `false` | Set by migration for groups that could not be auto-converted (invalid-only), or by import for apparent downgrades pending confirmation. |
| `updated_at` | **ADD** `DateTime`, default/onupdate `utcnow` | For provenance/audit display. |
| `version_match` | **RETAIN** (legacy) | No longer used by evaluation; kept as migration provenance only. |
| `status` | **RETAIN** (legacy) | Same — ignored by new logic. |

**Semantics**: one effective threshold per `(vendor, model)`. When several actual versions are recorded for the same vendor/model, the **minimal** is the stored `min_version` (FR-005) — the migration and import compute this with the D1 comparator before writing. `product` was replaced by `type` (migration `0005_device_type`): compliance matching (`compliance/version_check.py`) looks up a threshold by `vendor`(+`model`) substring-matched against the scanned banner string — `type` is never part of that match key, since a device-type category cannot be expected to appear in a banner.

**Validation**: `vendor` required; `type` required and must be one of `ip_phone | voip_gateway | ata | ucm | switch | router`; `min_version` must be a comparator-parseable version when present; `source ∈ {manual, ingested}`.

## 2. `VersionIngestionSource` (NEW) — tracked ingestion entry

Table `version_ingestion_sources`. Configured by administrators in Configuration Subtab 2 (FR-014).

| Column | Type | Notes |
|--------|------|-------|
| `id` | `String(36)` PK (uuid) | |
| `vendor` | `String(128)`, indexed | Vendor name. |
| `source_url` | `String(512)` | Official site/URL the fetcher reads (used by the staging CLI; the app only stores it). |
| `models` | `JSON` list | Product model(s) to track for this vendor. |
| `extractor` | `JSON`, default `{}` | Pluggable extraction config consumed by the staging fetcher (selector/regex + normalization). Opaque to the app. |
| `last_import_status` | `String(16)`, nullable | `ok` / `partial` / `failed` / null (never imported). |
| `last_import_at` | `DateTime`, nullable | |
| `last_versions` | `JSON`, default `{}` | Last imported `{model: version}` for display/diff. |
| `created_by` | `String(36)` FK→`operator_accounts.id`, nullable | |
| `created_at` / `updated_at` | `DateTime` | |

## 3. `ComplianceFinding` (BEHAVIOR CHANGE, no column change) — immutable history

Table `compliance_findings` is unchanged structurally. For `control = version_validity`, `detail` now carries fixed inputs captured at scan time (FR-012a):

```json
{
  "checked_version": "7.4",
  "threshold": "9.0",
  "matched_vendor": "OpenSSH",
  "matched_model": null,
  "expected_valid": "OpenSSH 9.0",   // upgrade target shown on non-compliant rows (FR-007)
  "comparison": "below_threshold"     // below_threshold | at_or_above | not_comparable | no_threshold
}
```

- `result` and `detail` are written once and **never** recomputed when a threshold later changes.
- `expected_valid` is derived from the threshold at scan time so the non-compliant row's orange highlight + upgrade target (features 003 FR-012/013) keep working, read straight from the frozen finding.

## 4. Update Bundle (NEW, file artifact — not a DB table)

Produced by the staging fetcher, consumed by import. Full schema in [contracts/bundle-format.md](./contracts/bundle-format.md). Shape:

```json
{
  "payload": {
    "vendor": "OpenSSH",
    "generated_at": "2026-10-23T10:00:00Z",
    "entries": [
      {"model": "portable", "type": "router", "version": "9.9", "source": "https://...", "fetched_at": "...", "status": "ok"},
      {"model": "legacy",   "type": "router", "version": null,  "source": "https://...", "fetched_at": "...", "status": "failed", "reason": "source unreachable"}
    ]
  },
  "integrity": { "alg": "HMAC-SHA256", "digest": "<sha256 of canonical payload>", "mac": "<hmac>" }
}
```

Imported entries with `status != ok` are reported, never written as a value (FR-017/FR-020). The `integrity` envelope is verified before any write (FR-016a).

## 5. Audit (reuse)

No new enum. Manual threshold edits and bundle imports emit `AuditEventType.CONFIG_CHANGE`. Import `detail` example (no secrets/keys):

```json
{"action": "import", "vendor": "OpenSSH", "source_id": "…", "bundle_digest": "…",
 "created": 1, "updated": 2, "skipped_failed": 1, "flagged_downgrade": 0}
```

## Entity relationships

- `VersionIngestionSource` (1 vendor, N models) → drives creation/update of N `ReferenceVersionEntry` threshold rows on import (linked by `source_ref`).
- `ReferenceVersionEntry` threshold → consulted at scan time by `check_version`; the resulting `ComplianceFinding` copies the threshold value in, breaking the live dependency (immutable history).

## Migration rules (Alembic `0004`)

1. Add columns in §1 and create table in §2.
2. For each `(vendor, product)` group in existing rows: `min_version` = lowest `valid` version (D1 comparator; `N.*` → `N.0`); collapse to one row, `source="manual"`.
3. Group with only `invalid` rows → keep one row with `min_version=NULL`, `needs_review=true`.
4. Emit a summary (converted / flagged) for the upgrade log and the UI "needs review" surface.
5. `downgrade()` restores the dropped columns/table (best-effort; enumerated rows are not reconstructed — documented one-way data transform).

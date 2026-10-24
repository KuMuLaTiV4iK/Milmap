# HTTP API Delta: Version Dictionary Overhaul

All endpoints are session-authenticated. Role gating per FR-013/FR-014 and Constitution Principle VII. Errors use the existing `web/errors.py` helpers (`validation_error`, `api_error`). All mutations emit `CONFIG_CHANGE` audit events.

## A. Reference-version thresholds (manual) — `require_operator` (operators + admins)

Replaces the enumerated `version_match`/`status` payloads of feature 003 with a threshold payload.

### `GET /api/reference-versions`
List threshold entries. Item:
```json
{"id": "…", "vendor": "OpenSSH", "type": "router", "model": null,
 "min_version": "9.0", "note": "…", "source": "manual", "needs_review": false, "updated_at": "…"}
```
`type` is a device-type category (`ip_phone | voip_gateway | ata | ucm | switch | router`) — pure classification, never part of compliance matching (which uses `vendor`(+`model`) only; see compliance/version_check.py).

### `POST /api/reference-versions`  → 201
Body: `{vendor, type, model?, min_version, note?}`.
- `vendor`, `type` (must be one of the fixed set above), `min_version` required; `min_version` must be comparator-parseable → else `validation_error`.
- On success: create row (`source="manual"`), audit `{action:"create", entry_id, vendor}`.

### `PUT /api/reference-versions/{id}`
Body: same as POST. Updates the threshold; clears `needs_review`. 404 if missing. Audit `{action:"update", …}`.

### `DELETE /api/reference-versions/{id}` → 204
Audit `{action:"delete", entry_id}`.

**Immutable-history note**: these mutations affect only *future* evaluations. Existing `ComplianceFinding` rows are never recomputed (FR-012a).

## B. Ingestion sources (tracked entries) — `require_admin` (admins only)

### `GET /api/version-ingestion/sources`
List tracked sources:
```json
{"id":"…","vendor":"OpenSSH","source_url":"https://…","models":["portable"],
 "last_import_status":"ok","last_import_at":"…","last_versions":{"portable":"9.9"}}
```

### `POST /api/version-ingestion/sources` → 201
Body: `{vendor, source_url, models[], extractor?}`. Validates non-empty vendor/url/models. Audit `{action:"create_source", vendor}`.

### `PUT /api/version-ingestion/sources/{id}` / `DELETE …/{id}`
Update / remove a tracked source. 404 if missing. Audit `{action:"update_source"|"delete_source", …}`.

## C. Bundle import — `require_admin` (admins only)

### `POST /api/version-ingestion/import/preview`
Multipart or JSON upload of a bundle file.
1. Parse + **verify integrity** (recompute SHA-256 of canonical payload, verify HMAC with local pre-shared key). Failure → `400 api_error("bundle_invalid", …)`, **no writes**.
2. Return a review/diff (no writes yet):
```json
{"vendor":"OpenSSH","bundle_digest":"…",
 "changes":[
   {"model":"portable","type":"router","current":"9.0","incoming":"9.9","effect":"update","downgrade":false},
   {"model":"legacy","status":"failed","reason":"source unreachable"}],
 "verdict_changing": 1}
```

### `POST /api/version-ingestion/import/apply`
Body: the verified bundle (re-verified server-side) + explicit confirmation. Applies create/update to threshold rows:
- `status != ok` entries are skipped (reported), never written (FR-017/FR-020).
- Apparent downgrades or verdict-changing entries require the confirmation flag; otherwise the row is written with `needs_review=true` and left for a second confirmation (FR-018).
- Each written row gets `source="ingested"`, `source_ref=<source id/url>`.
- Audit one `CONFIG_CHANGE` `{action:"import", vendor, source_id, bundle_digest, created, updated, skipped_failed, flagged_downgrade}` (no key/secret).

## D. Unchanged / reused
- `GET /reference-versions` page redirect → `/configuration` (feature 006 FR-013a) stays.
- Version-validity evaluation endpoint path is internal (`compliance/evaluate.py`), not an HTTP surface; it performs **zero** network calls (FR-008).

# Contract: Version Update Bundle Format

The offline-transferable artifact produced by the staging fetcher (one vendor + its models) and consumed by the air-gapped import (FR-016/FR-016a). A single UTF-8 JSON file.

## Structure

```json
{
  "schema": "milmap.version-bundle/1",
  "payload": {
    "vendor": "OpenSSH",
    "generated_at": "2026-10-23T10:00:00Z",
    "entries": [
      {"model": "portable", "type": "ip_phone", "version": "9.9",  "source": "https://www.openssh.com/", "fetched_at": "2026-10-23T10:00:00Z", "status": "ok"},
      {"model": "legacy",   "type": "ip_phone", "version": null,    "source": "https://www.openssh.com/", "fetched_at": "2026-10-23T10:00:00Z", "status": "failed", "reason": "source unreachable"}
    ]
  },
  "integrity": {
    "alg": "HMAC-SHA256",
    "digest": "<hex sha256 of the canonical payload>",
    "mac": "<hex hmac-sha256 of the canonical payload, key = local pre-shared key>",
    "key_id": "milmap-2026"
  }
}
```

> **TEMPORARY (explicit request, 2026-10-23)**: the `integrity` block is currently **optional** — a bundle with no `integrity` key is accepted without verification, so a bundle can be hand-composed before the signing tooling is finished. When `integrity` IS present it is still fully verified (rule 2 below is unchanged for that case). Re-tighten `integrity` to required once end-to-end signing is wired up — this reopens the FR-016a gap (an unsigned bundle's authenticity/integrity is not checked at all).

## Rules

1. **Canonicalization**: `payload` is serialized canonically (sorted keys, no insignificant whitespace, UTF-8) before hashing/HMAC, so staging and deployment compute identical bytes. Both sides MUST use the same canonicalization.
2. **Integrity (verified on import, before any write, WHEN `integrity` is present — see temporary note above)**:
   - Recompute SHA-256 over the canonical `payload`; MUST equal `integrity.digest`.
   - Recompute HMAC-SHA256 over the same bytes with the local pre-shared key selected by `key_id`; MUST equal `integrity.mac`.
   - Any mismatch, unknown `key_id`, missing field (when `integrity` is present), or unparseable JSON → **reject**, no threshold changed (FR-016a).
3. **Key handling**: the pre-shared key lives in local secure config on both machines, keyed by `key_id`. It is NEVER included in the bundle, logged, or returned in any API/audit detail (Principle II/IV).
4. **Per-entry status** (FR-017/FR-020): `status ∈ {ok, failed}`. `ok` MUST carry a comparator-parseable `version` AND a `type` from the fixed device-type set below. `failed` MUST carry a `reason` and `version: null`; `type` is optional on a `failed` entry (e.g. the failure IS a missing/invalid type) and never fabricated. Import reports a `failed` entry and makes **no** write for that model.
5. **Device type** (follow-up to the V0.7 overhaul): each `ok` entry's `type` is one of `ip_phone | voip_gateway | ata | ucm | switch | router` — a physical-device category. It is pure classification: it is NEVER used to match a scanned device (a category string like "ip_phone" cannot be expected to appear in a scanned service/firmware banner) — matching uses `vendor`(+`model`) only (see compliance/version_check.py). An unrecognized/missing `type` on an `ok` entry is rejected at import.
6. **Scope**: exactly one `vendor` per bundle (per clarified per-vendor fetch). Several vendors → several bundles.
7. **Versioning**: `schema` identifies the format; the importer rejects unknown major schema versions rather than guessing.

## Non-goals
- The bundle carries no credentials, keys, or app state — only version facts + integrity envelope.
- No transport is defined; the admin moves the file by whatever approved offline means (USB, one-way transfer).

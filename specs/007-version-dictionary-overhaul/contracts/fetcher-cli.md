# Contract: Standalone Staging Fetcher CLI

`tools/version_fetcher/` — run on a **separate, internet-connected staging machine**, NOT inside the air-gapped deployment and never imported by `src/asset_dashboard/` (Constitution Principle I; research D5). It is the only component permitted to make outbound network requests.

## Invocation

```
python -m version_fetcher fetch \
  --vendor "OpenSSH" \
  --source-url "https://www.openssh.com/releasenotes.html" \
  --models portable,legacy \
  --extractor extractor.json \
  --key-file ./milmap.key --key-id milmap-2026 \
  --out openssh-2026-10-23.bundle.json
```

- One invocation handles **one vendor** and its listed models (FR-015).
- `--extractor` points to the pluggable extraction config (CSS selector / regex + normalization) for this source; mirrors the `extractor` stored on the `VersionIngestionSource` so staging and app agree on what to pull.
- `--key-file` / `--key-id` select the pre-shared HMAC key used to sign the bundle (same key provisioned on the deployment).

## Behavior

1. Fetch the `--source-url`, apply the extractor per model to obtain a current version string.
2. Per model, emit an entry: `status:"ok"` + `version` on success; `status:"failed"` + `reason`, `version:null` on unreachable / timeout / unparseable / empty extraction (FR-017) — one failing model never aborts the others, and never fabricates a version (FR-020).
3. Normalize versions so they are comparator-parseable by the app's `version_compare` (research D1); if normalization can't produce a clean version, that model is `failed`.
4. Write the bundle (see [bundle-format.md](./bundle-format.md)): canonicalize `payload`, compute SHA-256 + HMAC-SHA256, write JSON to `--out`.

## Exit codes
- `0` — bundle written (even if some models failed; failures are inside the bundle).
- `2` — fatal (bad args, missing key, cannot write output). No partial bundle left.

## Guarantees / boundaries
- The CLI performs **all** internet access; the air-gapped app only reads the resulting file.
- No app DB access, no shared runtime import. It may use a vendored HTTP client (e.g. `httpx`) that the web app does not depend on.
- The signing key is read from `--key-file`, never written into the bundle or any log.

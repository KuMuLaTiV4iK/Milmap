"""Per-vendor fetch core (contracts/fetcher-cli.md). Runs on the SEPARATE
internet-connected staging machine — this module is the only place in the
repository that is allowed to make an outbound network request.
"""
from __future__ import annotations

from datetime import UTC, datetime

import httpx

from version_fetcher.extractors.base import ExtractionFailed, extract_version


def _resolve_type(extractor: dict, model: str) -> str | None:
    """The device-type category is static per-model metadata (not fetched)
    — it lives alongside the model's extraction config so one config file
    covers both. Free-form text (any non-empty string; the app's bundle
    importer does not restrict it to a fixed set — see
    version_ingestion/bundle.py). Returns None if missing/empty; the
    caller reports that model as `failed` rather than emitting an
    unclassified entry (the app's bundle importer rejects an 'ok' entry
    without a non-empty `type`)."""
    model_config = (extractor or {}).get(model) or (extractor or {}).get("default") or {}
    device_type = model_config.get("type")
    return device_type.strip() if isinstance(device_type, str) and device_type.strip() else None


def fetch_vendor(
    vendor: str,
    source_url: str,
    models: list[str],
    extractor: dict,
    *,
    timeout: float = 10.0,
) -> dict:
    """Fetch `source_url` once and extract a version per model. One failing
    model never aborts the others (FR-017); no model's version is ever
    fabricated (FR-020)."""
    fetched_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    entries = []

    try:
        response = httpx.get(source_url, timeout=timeout, follow_redirects=True)
        response.raise_for_status()
        html = response.text
        fetch_error: str | None = None
    except httpx.HTTPError as exc:
        html = ""
        fetch_error = f"source unreachable: {exc}"

    for model in models:
        device_type = _resolve_type(extractor, model)
        if device_type is None:
            entries.append(
                {
                    "model": model,
                    "type": None,
                    "version": None,
                    "source": source_url,
                    "fetched_at": fetched_at,
                    "status": "failed",
                    "reason": "no valid 'type' configured for this model",
                }
            )
            continue
        if fetch_error is not None:
            entries.append(
                {
                    "model": model,
                    "type": device_type,
                    "version": None,
                    "source": source_url,
                    "fetched_at": fetched_at,
                    "status": "failed",
                    "reason": fetch_error,
                }
            )
            continue
        try:
            version = extract_version(html, extractor, model)
        except ExtractionFailed as exc:
            entries.append(
                {
                    "model": model,
                    "type": device_type,
                    "version": None,
                    "source": source_url,
                    "fetched_at": fetched_at,
                    "status": "failed",
                    "reason": str(exc),
                }
            )
            continue
        entries.append(
            {
                "model": model,
                "type": device_type,
                "version": version,
                "source": source_url,
                "fetched_at": fetched_at,
                "status": "ok",
            }
        )

    return {"vendor": vendor, "generated_at": fetched_at, "entries": entries}

"""Pluggable per-model version extraction (research D7): a small config —
CSS selector or regex, plus a normalization rule — stored with the
tracked source. Config is data; this module is the only interpreter.
"""
from __future__ import annotations

import re


class ExtractionFailed(Exception):
    """Raised when extraction yields nothing usable. The caller records a
    per-model `failed` entry (FR-017) — it never fabricates a version."""


def extract_version(html: str, extractor: dict, model: str) -> str:
    """Apply the extractor config for `model` and return a normalized
    version string, or raise ExtractionFailed."""
    model_config = (extractor or {}).get(model) or (extractor or {}).get("default")
    if not model_config:
        raise ExtractionFailed(f"no extractor configured for model {model!r}")

    pattern = model_config.get("regex")
    if pattern:
        match = re.search(pattern, html)
        if not match:
            raise ExtractionFailed(f"regex {pattern!r} did not match")
        version = match.group(1) if match.groups() else match.group(0)
        return _normalize(version, model_config)

    selector = model_config.get("selector")
    if selector:
        return _extract_by_selector(html, selector, model_config)

    raise ExtractionFailed("extractor config has neither 'regex' nor 'selector'")


def _extract_by_selector(html: str, selector: str, model_config: dict) -> str:
    """Minimal CSS-selector-by-attribute extraction: `selector` names an
    HTML element id or class whose text content is scanned with the
    model's `regex` (if given) or taken verbatim. Kept intentionally small
    — this CLI is meant to be extended per-vendor via config, not by
    growing a full CSS engine here."""
    id_match = re.search(rf'id="{re.escape(selector)}"[^>]*>([^<]+)<', html)
    if not id_match:
        raise ExtractionFailed(f"selector {selector!r} not found")
    text = id_match.group(1).strip()
    return _normalize(text, model_config)


def _normalize(version: str, model_config: dict) -> str:
    strip_prefix = model_config.get("strip_prefix")
    if strip_prefix and version.startswith(strip_prefix):
        version = version[len(strip_prefix) :]
    version = version.strip()
    if not version:
        raise ExtractionFailed("normalization produced an empty version")
    return version

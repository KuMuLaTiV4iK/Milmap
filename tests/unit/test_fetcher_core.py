"""Unit tests for the out-of-runtime staging fetcher core (contracts/
fetcher-cli.md): per-model ok/failed, no fabricated version on failure.

`tools/` is not on the app's `pythonpath` (it is deliberately NOT part of
the air-gapped runtime package) — this test adds it to `sys.path` itself,
exactly as a developer running the CLI from `tools/` would.
"""

import sys
from pathlib import Path

import httpx
import pytest

TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from version_fetcher.extractors.base import ExtractionFailed, extract_version  # noqa: E402
from version_fetcher.fetch import fetch_vendor  # noqa: E402

SAMPLE_HTML = '<html><body>Current release: <span id="version">9.9</span></body></html>'


def test_extract_version_by_regex():
    extractor = {"portable": {"regex": r'id="version">([\d.]+)<'}}
    assert extract_version(SAMPLE_HTML, extractor, "portable") == "9.9"


def test_extract_version_by_selector():
    extractor = {"portable": {"selector": "version"}}
    assert extract_version(SAMPLE_HTML, extractor, "portable") == "9.9"


def test_extract_version_missing_config_fails():
    with pytest.raises(ExtractionFailed):
        extract_version(SAMPLE_HTML, {}, "portable")


def test_fetch_vendor_ok_and_failed_models(monkeypatch):
    class _FakeResponse:
        text = SAMPLE_HTML

        def raise_for_status(self):
            pass

    monkeypatch.setattr(httpx, "get", lambda *a, **k: _FakeResponse())

    extractor = {"portable": {"regex": r'id="version">([\d.]+)<', "type": "router"}}
    bundle_payload = fetch_vendor(
        "OpenSSH", "https://example.invalid/", ["portable", "legacy"], extractor
    )

    by_model = {e["model"]: e for e in bundle_payload["entries"]}
    assert by_model["portable"]["status"] == "ok"
    assert by_model["portable"]["version"] == "9.9"
    assert by_model["portable"]["type"] == "router"
    assert by_model["legacy"]["status"] == "failed"
    assert by_model["legacy"]["version"] is None
    assert by_model["legacy"]["reason"]  # no 'type' configured for this model


def test_fetch_vendor_model_with_empty_type_fails_without_fabricating():
    extractor = {"portable": {"regex": r'id="version">([\d.]+)<', "type": "  "}}
    bundle_payload = fetch_vendor("OpenSSH", "https://example.invalid/", ["portable"], extractor)
    entry = bundle_payload["entries"][0]
    assert entry["status"] == "failed"
    assert entry["version"] is None


def test_fetch_vendor_accepts_a_free_form_type(monkeypatch):
    class _FakeResponse:
        text = SAMPLE_HTML

        def raise_for_status(self):
            pass

    monkeypatch.setattr(httpx, "get", lambda *a, **k: _FakeResponse())
    extractor = {"portable": {"regex": r'id="version">([\d.]+)<', "type": "UCM.Sys"}}
    bundle_payload = fetch_vendor(
        "Grandstream", "https://example.invalid/", ["portable"], extractor
    )
    entry = bundle_payload["entries"][0]
    assert entry["status"] == "ok"
    assert entry["type"] == "UCM.Sys"


def test_fetch_vendor_unreachable_source_fails_all_models(monkeypatch):
    def _raise(*a, **k):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx, "get", _raise)

    bundle_payload = fetch_vendor("OpenSSH", "https://example.invalid/", ["portable"], {})
    entry = bundle_payload["entries"][0]
    assert entry["status"] == "failed"
    assert entry["version"] is None

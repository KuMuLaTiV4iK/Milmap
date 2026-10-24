"""Feature 010 — tactical-HUD redesign: static presentation invariants.

Guards the binding invariants of the design-system contract: air-gapped
(no off-origin asset URL), CSP unchanged, local-only Volja @font-face, a
single aria-hidden decoration layer, and text on every status badge.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from asset_dashboard.web import security_headers

_CSS = Path(security_headers.__file__).parent / "static" / "base.css"

# CSP baseline captured before the redesign (invariant I2).
_CSP_BASELINE = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self'; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)

_PAGES = ["/", "/profiles", "/history", "/schedules", "/tools/credential-check", "/configuration", "/scan"]
# Asset-loading tags only; the footer project <a href> is a navigation link.
_ASSET_TAG = re.compile(r'<(?:link|script|img|source|iframe)[^>]*(?:src|href)="(?:https?:)?//', re.I)


def _get(client, path):
    return client.get(path, headers={"accept": "text/html"})


def test_stylesheet_has_no_off_origin_or_data_urls():
    css = _CSS.read_text(encoding="utf-8")
    assert not re.search(r"url\(\s*['\"]?(https?:)?//", css)
    assert not re.search(r"url\(\s*['\"]?data:", css, re.I)


def test_font_face_sources_are_local_static_fonts():
    css = _CSS.read_text(encoding="utf-8")
    faces = re.findall(r"@font-face\s*\{[^}]*\}", css)
    assert faces, "Volja @font-face missing"
    urls = [u for face in faces for u in re.findall(r"url\(\s*['\"]?([^'\")]+)", face)]
    assert urls and all(u.startswith("/static/fonts/") for u in urls)
    assert "font-display: swap" in css


def test_csp_header_unchanged(authed_client):
    assert _get(authed_client, "/").headers["content-security-policy"] == _CSP_BASELINE


@pytest.mark.parametrize("path", _PAGES)
def test_pages_have_single_decoration_layer_and_no_external_assets(authed_client, path):
    resp = _get(authed_client, path)
    assert resp.status_code == 200
    text = resp.text
    assert text.count('class="hud-decoration"') == 1
    assert 'class="hud-decoration" aria-hidden="true"' in text
    # Decoration is the first <body> child, behind the header and content.
    assert text.index("hud-decoration") < text.index("<main")
    assert not _ASSET_TAG.search(text)


def test_login_page_has_decoration_layer(client):
    text = client.get("/login", headers={"accept": "text/html"}).text
    assert text.count('class="hud-decoration"') == 1


def test_status_badges_always_carry_text(authed_client):
    for path in ("/", "/history"):
        text = _get(authed_client, path).text
        for m in re.finditer(r'<span class="badge[^"]*">(.*?)</span>', text, re.S):
            assert m.group(1).strip(), f"empty badge on {path}"

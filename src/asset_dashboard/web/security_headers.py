"""Baseline security response headers for every request.

Defense-in-depth for a locally-hosted admin tool: these don't replace the
auth gate (auth/sessions.py) but reduce the blast radius of any XSS/
clickjacking/MIME-sniffing issue in the server-rendered pages.
"""
from __future__ import annotations

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

# Self-hosted only: no CDN, no inline-script-from-elsewhere, matching the
# air-gapped constraint (no external script/style/font/connect sources).
_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "  # templates use small inline <script> blocks
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self'; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = _CSP
        # Not Strict-Transport-Security by default: this app is typically
        # served over plain HTTP on a trusted local/internal segment with
        # no TLS termination out of the box (see auth/sessions.py's cookie
        # `secure=False` default) — forcing HSTS here would be misleading.
        return response

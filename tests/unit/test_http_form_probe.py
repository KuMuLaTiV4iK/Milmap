"""Unit tests for the form-aware HTTP/HTTPS probe (US3, SC-003, FR-105-FR-107).

The probe must GET the login page (fingerprint) and then POST the credential
to the configured login path, judge success/rejection by the configured
status/keywords, tolerate self-signed TLS on HTTPS (verify=False), and never
leak the attempted secret into the response excerpt.
"""
from __future__ import annotations

from urllib.parse import parse_qs

import httpx

from asset_dashboard.compliance.probes import http as http_probe

CORRECT = {"username": "admin", "secret": "s3cr3t-value"}


def _install_mock(monkeypatch, record):
    """Route the probe's httpx.Client through a MockTransport form server and
    record the `verify` kwarg the probe passed."""

    def handler(request: httpx.Request) -> httpx.Response:
        record["requests"].append((request.method, request.url.path))
        if request.method == "GET":
            return httpx.Response(
                200,
                html='<form method="post" action="/login">'
                '<input name="csrf_token" value="tok-123">'
                '<input name="username"><input name="password"></form>',
            )
        form = parse_qs(request.content.decode())
        user = (form.get("username") or [""])[0]
        pwd = (form.get("password") or [""])[0]
        if user == CORRECT["username"] and pwd == CORRECT["secret"]:
            return httpx.Response(200, html="<h1>Dashboard</h1> Logout")
        return httpx.Response(401, html="Login failed")

    real_client = httpx.Client

    def client_factory(*args, **kwargs):
        record["verify"] = kwargs.get("verify")
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(http_probe.httpx, "Client", client_factory)


_PROBE_CONFIG = {
    "login_path": "/login",
    "method": "POST",
    "success": {"status": [200]},
    "failure": {"status": [401]},
}


def test_correct_credentials_accepted_after_get_then_post(monkeypatch):
    record = {"requests": [], "verify": None}
    _install_mock(monkeypatch, record)

    result = http_probe.attempt(
        "10.10.0.5", 80, CORRECT["username"], CORRECT["secret"], [], probe_config=_PROBE_CONFIG
    )

    assert record["requests"] == [("GET", "/login"), ("POST", "/login")]
    assert result.matched is True
    assert result.status == 200


def test_wrong_credentials_rejected(monkeypatch):
    record = {"requests": [], "verify": None}
    _install_mock(monkeypatch, record)

    result = http_probe.attempt(
        "10.10.0.5", 80, "admin", "wrong-password", [], probe_config=_PROBE_CONFIG
    )

    assert result.matched is False
    assert result.status == 401


def test_https_tolerates_self_signed_tls(monkeypatch):
    record = {"requests": [], "verify": None}
    _install_mock(monkeypatch, record)

    http_probe.attempt(
        "10.10.0.5", 443, CORRECT["username"], CORRECT["secret"], [],
        scheme="https", probe_config=_PROBE_CONFIG,
    )

    assert record["verify"] is False  # self-signed internal certs are tolerated


def test_excerpt_never_contains_the_secret(monkeypatch):
    record = {"requests": [], "verify": None}
    _install_mock(monkeypatch, record)

    result = http_probe.attempt(
        "10.10.0.5", 80, CORRECT["username"], CORRECT["secret"], [], probe_config=_PROBE_CONFIG
    )

    assert CORRECT["secret"] not in (result.response_excerpt or "")


def test_csrf_token_is_captured_and_submitted(monkeypatch):
    """When probe_config.csrf points at a hidden input, the probe captures the
    token from the GET page and carries it into the POST."""
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200, html='<input name="csrf_token" value="tok-123">'
            )
        form = parse_qs(request.content.decode())
        seen["csrf"] = (form.get("csrf_token") or [""])[0]
        return httpx.Response(200, html="Dashboard")

    real_client = httpx.Client

    def client_factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(http_probe.httpx, "Client", client_factory)

    cfg = {
        **_PROBE_CONFIG,
        "csrf": {"source": "input", "name": "csrf_token", "field": "csrf_token"},
    }
    http_probe.attempt("10.10.0.5", 80, "admin", "x", [], probe_config=cfg)
    assert seen["csrf"] == "tok-123"

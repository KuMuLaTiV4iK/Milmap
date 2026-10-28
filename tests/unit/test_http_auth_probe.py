"""Unit tests for the HTTP Basic/Digest credential probe (feature 009).

These cover the native-dialog auth flow used by embedded web UIs (IP phones,
cameras, switches): the probe first asks the host which scheme it wants via the
`WWW-Authenticate` challenge, then authenticates with Basic or Digest. The
real-world bug that motivated this: a device behind HTTP Basic auth with valid
`viewer:viewer` was reported as a non-match because the form-only probe POSTed
to a non-existent `/login` and got a 404.
"""

from __future__ import annotations

import base64

import httpx

from asset_dashboard.compliance.probes import http as http_probe

CORRECT = {"username": "viewer", "secret": "viewer"}


def _basic_server(record, *, scheme="Basic"):
    """A MockTransport handler for a host guarded by HTTP Basic auth.

    First (unauthenticated) GET -> 401 + WWW-Authenticate challenge; a GET
    carrying the correct Basic credential -> 200; anything else -> 401.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        record["requests"].append((request.method, request.url.path))
        auth = request.headers.get("Authorization")
        if not auth:
            return httpx.Response(401, headers={"WWW-Authenticate": f'{scheme} realm="phone"'})
        try:
            raw = base64.b64decode(auth.split(" ", 1)[1]).decode()
            user, _, pwd = raw.partition(":")
        except (ValueError, IndexError):
            return httpx.Response(401)
        if user == CORRECT["username"] and pwd == CORRECT["secret"]:
            return httpx.Response(200, text="<html>Phone Status</html>")
        return httpx.Response(401, headers={"WWW-Authenticate": f'{scheme} realm="phone"'})

    return handler


def _install(monkeypatch, handler, record):
    real_client = httpx.Client

    def client_factory(*args, **kwargs):
        record["verify"] = kwargs.get("verify")
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(http_probe.httpx, "Client", client_factory)


_AUTO = {"auth": "auto", "auth_path": "/"}


def test_auto_negotiates_basic_and_accepts_correct_credential(monkeypatch):
    record = {"requests": [], "verify": None}
    _install(monkeypatch, _basic_server(record), record)

    result = http_probe.attempt(
        "10.10.0.9", 80, CORRECT["username"], CORRECT["secret"], [], probe_config=_AUTO
    )

    # One unauthenticated negotiation GET, then the authenticated GET.
    assert record["requests"] == [("GET", "/"), ("GET", "/")]
    assert result.matched is True
    assert result.status == 200


def test_auto_rejects_wrong_credential(monkeypatch):
    record = {"requests": [], "verify": None}
    _install(monkeypatch, _basic_server(record), record)

    result = http_probe.attempt("10.10.0.9", 80, "viewer", "wrong", [], probe_config=_AUTO)

    assert result.matched is False
    assert result.status == 401


def test_open_page_is_not_a_false_positive(monkeypatch):
    """A host that never challenges (200 on the bare GET) must not be flagged."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="open")

    record = {"requests": [], "verify": None}
    _install(monkeypatch, handler, record)

    result = http_probe.attempt(
        "10.10.0.9", 80, CORRECT["username"], CORRECT["secret"], [], probe_config=_AUTO
    )

    assert result.matched is False


def test_forced_basic_skips_negotiation_when_scheme_pinned(monkeypatch):
    """An operator-pinned `auth: basic` authenticates even if the host's
    challenge header is absent, and is not gated on prior challenge."""
    record = {"requests": [], "verify": None}

    def handler(request: httpx.Request) -> httpx.Response:
        record["requests"].append((request.method, request.url.path))
        auth = request.headers.get("Authorization")
        if not auth:
            return httpx.Response(401)  # no WWW-Authenticate header at all
        raw = base64.b64decode(auth.split(" ", 1)[1]).decode()
        user, _, pwd = raw.partition(":")
        if user == CORRECT["username"] and pwd == CORRECT["secret"]:
            return httpx.Response(200, text="ok")
        return httpx.Response(401)

    _install(monkeypatch, handler, record)

    result = http_probe.attempt(
        "10.10.0.9",
        80,
        CORRECT["username"],
        CORRECT["secret"],
        [],
        probe_config={"auth": "basic", "auth_path": "/"},
    )

    assert result.matched is True
    assert result.status == 200


def test_https_auth_tolerates_self_signed_tls(monkeypatch):
    record = {"requests": [], "verify": None}
    _install(monkeypatch, _basic_server(record), record)

    http_probe.attempt(
        "10.10.0.9",
        443,
        CORRECT["username"],
        CORRECT["secret"],
        [],
        scheme="https",
        probe_config=_AUTO,
    )

    assert record["verify"] is False  # self-signed internal certs tolerated


def test_excerpt_never_contains_the_secret(monkeypatch):
    record = {"requests": [], "verify": None}
    _install(monkeypatch, _basic_server(record), record)

    result = http_probe.attempt(
        "10.10.0.9", 80, CORRECT["username"], CORRECT["secret"], [], probe_config=_AUTO
    )

    assert CORRECT["secret"] not in (result.response_excerpt or "")

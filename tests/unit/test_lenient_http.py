"""Lenient-HTTP fallback tests against a REAL socket server (feature 009).

httpx/h11 rejects the doubled status line that Grandstream's mini_httpd CGI
emits (`RemoteProtocolError: illegal header line: HTTP/1.1 200 OK`), which
MockTransport cannot reproduce. So these tests run a tiny raw-socket server
that emits exactly that malformed response and verify the probe's raw fallback
parses it and authenticates — the real-world bug this all exists to fix.
"""

from __future__ import annotations

import socket
import threading
import time
import uuid
from urllib.parse import parse_qs

from asset_dashboard.compliance.probes import http as http_probe
from asset_dashboard.compliance.probes import lenient_http


def _clean(body: str) -> bytes:
    b = body.encode()
    return (
        b"HTTP/1.1 200 OK\r\nServer: mini_httpd/1.19\r\n"
        b"Content-Type: text/html; charset=utf-8\r\n"
        b"Content-Length: " + str(len(b)).encode() + b"\r\nConnection: close\r\n\r\n" + b
    )


def _doubled_status(body: str) -> bytes:
    """A mini_httpd CGI response with the DOUBLED status line h11 rejects."""
    b = body.encode()
    return (
        b"HTTP/1.1 200 OK\r\nHTTP/1.1 200 OK\r\nServer: mini_httpd/1.19\r\n"
        b"Content-Type: text/html; charset=utf-8\r\n"
        b"Content-Length: " + str(len(b)).encode() + b"\r\nConnection: close\r\n\r\n" + b
    )


def _not_found() -> bytes:
    body = b"<HTML><TITLE>404 Not Found</TITLE>File not found.</HTML>"
    return (
        b"HTTP/1.1 404 Not Found\r\nContent-Type: text/html\r\n"
        b"Content-Length: " + str(len(body)).encode() + b"\r\nConnection: close\r\n\r\n" + body
    )


_LOGIN_FORM = (
    '<html><body>{err}<form action="dologin" method="post" name="loginOutForm">'
    '<input name="session_token" type=hidden value="{tok}">'
    '<input type=text name="username" value="admin">'
    '<input name="P2" type=password>'
    '<input type="submit" name="Login" value="Login">'
    '<input name="gnkey" type=hidden value=0b82>'
    "</form></body></html>"
)

_STATUS_PAGE = (
    "<html><body>Grandstream Device Configuration STATUS BASIC SETTINGS "
    "ADVANCED SETTINGS FXS PORT MAC Address Core Dump: Clean</body></html>"
)


class _GrandstreamServer(threading.Thread):
    """Mimics the real HT801: "/" is a clean static page with a JS redirect;
    the CGI endpoints emit the doubled-status-line quirk that breaks h11."""

    def __init__(self, correct=("user", "123")):
        super().__init__(daemon=True)
        self._correct = correct
        self._tokens: set[str] = set()
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(16)
        self.port = self._sock.getsockname()[1]
        self._stop = False

    def run(self) -> None:
        while not self._stop:
            try:
                conn, _ = self._sock.accept()
            except OSError:
                return
            try:
                self._handle(conn)
            except OSError:
                pass
            finally:
                conn.close()

    def stop(self) -> None:
        self._stop = True
        try:
            self._sock.close()
        except OSError:
            pass

    def _handle(self, conn: socket.socket) -> None:
        conn.settimeout(3)
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = conn.recv(4096)
            if not chunk:
                return
            data += chunk
        head, _, rest = data.partition(b"\r\n\r\n")
        request_line = head.split(b"\r\n", 1)[0].decode("latin-1")
        method, path, _ = request_line.split(" ", 2)
        # read any POST body by Content-Length
        clen = 0
        for line in head.split(b"\r\n")[1:]:
            if line.lower().startswith(b"content-length:"):
                clen = int(line.split(b":", 1)[1].strip())
        while len(rest) < clen:
            rest += conn.recv(4096)

        if path == "/":
            conn.sendall(
                _clean(
                    '<html><head><script>window.location = "/cgi-bin/login";'
                    "</script></head><title>Grandstream Device Configuration</title></html>"
                )
            )
        elif path == "/cgi-bin/login":
            tok = uuid.uuid4().hex
            self._tokens.add(tok)
            conn.sendall(_doubled_status(_LOGIN_FORM.format(err="", tok=tok)))
        elif path.startswith("/cgi-bin/dologin"):
            form = {k: v[0] for k, v in parse_qs(rest.decode("latin-1")).items()}
            ok = (
                form.get("username") == self._correct[0]
                and form.get("P2") == self._correct[1]
                and form.get("session_token") in self._tokens
                and form.get("gnkey") == "0b82"
            )
            if ok:
                conn.sendall(_doubled_status(_STATUS_PAGE))
            else:
                conn.sendall(
                    _doubled_status(
                        _LOGIN_FORM.format(
                            err="Sorry. Your Login Password is not recognized. "
                            "Remaining Attempts: 1",
                            tok=uuid.uuid4().hex,
                        )
                    )
                )
        else:
            conn.sendall(_not_found())


def _lf_response(body: str, status: str = "200 OK") -> bytes:
    """A Grandstream/1.10-style CGI response: CRLF on the status line but BARE
    LF on the headers and the header/body separator, no Content-Length."""
    b = body.encode()
    return (
        b"HTTP/1.0 " + status.encode() + b"\r\n"
        b"Content-Type: text/html; charset=utf-8\n"
        b"Server: Grandstream/1.10\n"
        b"X-Frame-Options:SAMEORIGIN\n"
        b"X-Content-Type-Options: nosniff\n\n" + b
    )


_LOGIN_FORM_CSRF = (
    '<html><body>{err}<form action="dologin" method="post" name="loginErrForm">'
    '<input name="csrf_token" type=hidden value="{tok}">'
    '<input type=text name="username" value="admin">'
    '<input name="P2" type=password>'
    '<input type="submit" name="Login" value="Login">'
    '<input name="gnkey" type=hidden value=0b82>'
    "</form></body></html>"
)

_FAIL_TEXT = (
    "Sorry, your login password is not recognized, or you do not have access "
    "privilege. Please try again. Remaining Attempts: 4"
)


class _Grandstream110Server(_GrandstreamServer):
    """Newer firmware: bare-LF headers, csrf_token, single status line."""

    def _handle(self, conn: socket.socket) -> None:
        conn.settimeout(3)
        data = b""
        while b"\r\n\r\n" not in data and b"\n\n" not in data:
            chunk = conn.recv(4096)
            if not chunk:
                return
            data += chunk
        norm = data.replace(b"\r\n", b"\n")
        head, _, rest = norm.partition(b"\n\n")
        method, path, _ = head.split(b"\n", 1)[0].decode("latin-1").split(" ", 2)
        clen = 0
        for line in head.split(b"\n")[1:]:
            if line.lower().startswith(b"content-length:"):
                clen = int(line.split(b":", 1)[1].strip())
        while len(rest) < clen:
            rest += conn.recv(4096)

        if path == "/":
            conn.sendall(
                _clean(
                    '<html><head><script>window.location = "/cgi-bin/login";'
                    "</script></head></html>"
                )
            )
        elif path == "/cgi-bin/login":
            tok = uuid.uuid4().hex
            self._tokens.add(tok)
            conn.sendall(_lf_response(_LOGIN_FORM_CSRF.format(err="", tok=tok)))
        elif path.startswith("/cgi-bin/dologin"):
            form = {k: v[0] for k, v in parse_qs(rest.decode("latin-1")).items()}
            ok = (
                form.get("username") == self._correct[0]
                and form.get("P2") == self._correct[1]
                and form.get("csrf_token") in self._tokens
            )
            if ok:
                conn.sendall(_lf_response(_STATUS_PAGE))
            else:
                conn.sendall(
                    _lf_response(_LOGIN_FORM_CSRF.format(err=_FAIL_TEXT, tok=uuid.uuid4().hex))
                )
        else:
            conn.sendall(_not_found())


def test_raw_fetch_handles_bare_lf_headers():
    """A bare-LF CGI response must parse its body, not swallow it as headers."""
    srv = _Grandstream110Server()
    srv.start()
    try:
        r = lenient_http.raw_fetch(
            "GET", f"http://127.0.0.1:{srv.port}/cgi-bin/login", {}, None, 3.0
        )
        assert r is not None and r.status_code == 200
        assert "csrf_token" in r.text
        assert 'name="P2"' in r.text
    finally:
        srv.stop()


def test_auto_probe_bare_lf_device_no_false_positive():
    """Regression for the false positive: with bare-LF parsing fixed, a WRONG
    credential's 'not recognized' page is seen and rejected; only the correct
    credential (carrying the discovered csrf_token) matches."""
    srv = _Grandstream110Server(correct=("viewer", "viewer"))
    srv.start()
    try:
        bad = http_probe.attempt("127.0.0.1", srv.port, "admin", "admin", [], probe_config={})
        assert bad.matched is False, f"false positive: excerpt={bad.response_excerpt!r}"
        assert "not recognized" in (bad.response_excerpt or "").lower()

        ok = http_probe.attempt("127.0.0.1", srv.port, "viewer", "viewer", [], probe_config={})
        assert ok.matched is True, f"status={ok.status} excerpt={ok.response_excerpt!r}"
    finally:
        srv.stop()


class _ThrottledServer(_Grandstream110Server):
    """Like the newer firmware, but DELAYS the dologin response ~1.2s to mimic
    the device's anti-bruteforce throttling (the real HT801 delayed ~14s)."""

    def _handle(self, conn: socket.socket) -> None:
        # Peek the path quickly, then delay only the login POST.
        conn.settimeout(3)
        data = b""
        while b"\r\n\r\n" not in data and b"\n\n" not in data:
            chunk = conn.recv(4096)
            if not chunk:
                return
            data += chunk
        if b"/cgi-bin/dologin" in data.split(b"\n", 1)[0]:
            time.sleep(1.2)
        # Re-dispatch using the collected request (handle expects to read it
        # itself, so hand the socket back by processing inline is simplest):
        self._dispatch(conn, data)

    def _dispatch(self, conn: socket.socket, data: bytes) -> None:
        norm = data.replace(b"\r\n", b"\n")
        head, _, rest = norm.partition(b"\n\n")
        method, path, _ = head.split(b"\n", 1)[0].decode("latin-1").split(" ", 2)
        clen = 0
        for line in head.split(b"\n")[1:]:
            if line.lower().startswith(b"content-length:"):
                clen = int(line.split(b":", 1)[1].strip())
        while len(rest) < clen:
            rest += conn.recv(4096)
        if path == "/":
            conn.sendall(
                _clean(
                    '<html><head><script>window.location = "/cgi-bin/login";'
                    "</script></head></html>"
                )
            )
        elif path == "/cgi-bin/login":
            tok = uuid.uuid4().hex
            self._tokens.add(tok)
            conn.sendall(_lf_response(_LOGIN_FORM_CSRF.format(err="", tok=tok)))
        elif path.startswith("/cgi-bin/dologin"):
            form = {k: v[0] for k, v in parse_qs(rest.decode("latin-1")).items()}
            ok = (
                form.get("username") == self._correct[0]
                and form.get("P2") == self._correct[1]
                and form.get("csrf_token") in self._tokens
            )
            conn.sendall(
                _lf_response(_STATUS_PAGE)
                if ok
                else _lf_response(_LOGIN_FORM_CSRF.format(err=_FAIL_TEXT, tok=uuid.uuid4().hex))
            )
        else:
            conn.sendall(_not_found())


def test_auto_probe_waits_out_throttled_login_response():
    """Regression: the device delays the login response; the probe must wait
    (long read timeout) instead of giving up and reporting a transport None."""
    srv = _ThrottledServer(correct=("viewer", "viewer"))
    srv.start()
    try:
        ok = http_probe.attempt("127.0.0.1", srv.port, "viewer", "viewer", [], probe_config={})
        assert ok.matched is True, f"status={ok.status} excerpt={ok.response_excerpt!r}"
    finally:
        srv.stop()


def test_raw_fetch_tolerates_doubled_status_line():
    srv = _GrandstreamServer()
    srv.start()
    try:
        r = lenient_http.raw_fetch(
            "GET", f"http://127.0.0.1:{srv.port}/cgi-bin/login", {}, None, 3.0
        )
        assert r is not None
        assert r.status_code == 200
        assert "<form" in r.text.lower()
        assert 'name="P2"' in r.text
    finally:
        srv.stop()


def test_auto_probe_authenticates_against_mini_httpd_quirk():
    """The full probe against a server that breaks httpx: correct creds match,
    wrong creds don't, and the failure shows the device's rejection text."""
    srv = _GrandstreamServer(correct=("user", "123"))
    srv.start()
    try:
        ok = http_probe.attempt("127.0.0.1", srv.port, "user", "123", [], probe_config={})
        assert ok.matched is True, f"status={ok.status} excerpt={ok.response_excerpt!r}"

        bad = http_probe.attempt("127.0.0.1", srv.port, "user", "nope", [], probe_config={})
        assert bad.matched is False
        assert "not recognized" in (bad.response_excerpt or "").lower()
    finally:
        srv.stop()

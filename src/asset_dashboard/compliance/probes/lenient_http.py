"""Lenient HTTP fetch for crusty embedded web servers (feature 009).

Some device management servers — notably Grandstream's `mini_httpd/1.19`
(2003) — emit CGI responses with a DOUBLED status line:

    HTTP/1.1 200 OK\r\n      <- mini_httpd's own status line
    HTTP/1.1 200 OK\r\n      <- the CGI script ALSO prints one
    Server: ...\r\n
    ...

httpx's strict HTTP/1.1 parser (h11) raises `RemoteProtocolError: illegal
header line` on the second status line and discards the whole response, so the
login page and the credential POST are both invisible to it. `curl` and real
browsers tolerate this. There is no lenient mode in h11, so this module
provides a minimal raw-socket client that tolerates the quirk, and a `Fetcher`
that uses httpx normally but falls back to the raw path on a protocol error.

Scope is deliberately small: enough to drive the credential probe (GET/POST,
cookies, Location redirects, Content-Length / chunked / read-until-close,
optional TLS with verification disabled for self-signed internal certs). It is
NOT a general HTTP client.
"""

from __future__ import annotations

import base64
import socket
import ssl
import time
from urllib.parse import urlencode, urljoin, urlsplit

import httpx


class Response:
    """A minimal, httpx-shaped response the probe code can consume uniformly."""

    __slots__ = ("status_code", "text", "url", "headers", "set_cookies")

    def __init__(
        self,
        status_code: int,
        text: str,
        url: str,
        headers: dict[str, str],
        set_cookies: list[str],
    ) -> None:
        self.status_code = status_code
        self.text = text
        self.url = url
        self.headers = headers  # keys lowercased
        self.set_cookies = set_cookies

    def header(self, name: str, default: str = "") -> str:
        return self.headers.get(name.lower(), default)


def _parse_url(url: str) -> tuple[str, str, int, str]:
    u = urlsplit(url)
    scheme = u.scheme or "http"
    host = u.hostname or ""
    port = u.port or (443 if scheme == "https" else 80)
    path = u.path or "/"
    if u.query:
        path += "?" + u.query
    return scheme, host, port, path


def _dechunk(body: bytes) -> bytes:
    out = bytearray()
    i = 0
    try:
        while i < len(body):
            j = body.find(b"\r\n", i)
            if j == -1:
                break
            size = int(body[i:j].split(b";")[0], 16)
            if size == 0:
                break
            start = j + 2
            out += body[start : start + size]
            i = start + size + 2  # skip trailing CRLF
    except ValueError:
        return bytes(body)
    return bytes(out)


def raw_fetch(
    method: str,
    url: str,
    headers: dict[str, str],
    body: bytes | None,
    timeout: float,
    verify: bool = True,
    connect_timeout: float | None = None,
) -> Response | None:
    """Fetch `url` over a raw socket, tolerating a doubled HTTP status line.

    `timeout` is the READ budget — embedded devices deliberately delay a login
    response (anti-bruteforce; an HT801 took ~14s), so it must be generous.
    `connect_timeout` (default: min(timeout, 8)) fails fast on a dead host.
    Returns a `Response`, or None on any socket/TLS error. Always sends
    `Connection: close` so the body can be read until the server closes."""
    conn_to = connect_timeout if connect_timeout is not None else min(timeout, 8.0)
    scheme, host, port, path = _parse_url(url)
    sent = {k.lower() for k in headers}
    lines = [f"{method} {path} HTTP/1.1", f"Host: {host}"]
    lines += [f"{k}: {v}" for k, v in headers.items()]
    if "connection" not in sent:
        lines.append("Connection: close")
    if "accept-encoding" not in sent:
        lines.append("Accept-Encoding: identity")  # avoid gzip we can't inflate
    if body is not None:
        if "content-length" not in sent:
            lines.append(f"Content-Length: {len(body)}")
        if "content-type" not in sent:
            lines.append("Content-Type: application/x-www-form-urlencoded")
    request = ("\r\n".join(lines) + "\r\n\r\n").encode("latin-1")
    if body:
        request += body

    # Connect/send/read, retrying ONCE only when the request never left the
    # socket (a true connection failure — common right after httpx freed a slot
    # on a tiny embedded server). If the send succeeded we never retry, so a
    # login POST is never double-submitted.
    raw = b""
    for attempt_i in range(2):
        sock = None
        sent_ok = False
        try:
            sock = socket.create_connection((host, port), timeout=conn_to)
            if scheme == "https":
                ctx = ssl.create_default_context()
                if not verify:
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                sock = ctx.wrap_socket(sock, server_hostname=host)
            sock.settimeout(timeout)
            sock.sendall(request)
            sent_ok = True
            chunks: list[bytes] = []
            while True:
                try:
                    buf = sock.recv(65536)
                except TimeoutError:
                    break
                if not buf:
                    break
                chunks.append(buf)
            raw = b"".join(chunks)
        except OSError:
            raw = b""
        finally:
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass
        if raw or sent_ok:
            break
        if attempt_i == 0:
            time.sleep(0.3)

    if not raw:
        return None

    # Header/body boundary — tolerate CRLF, bare LF, and mixes. These device
    # CGIs terminate headers with bare "\n" (and even mix "\r\n" on the status
    # line with "\n" on the rest), so a strict "\r\n\r\n" split fails and the
    # whole body is lost. Pick the EARLIEST of the two boundaries.
    idx_crlf = raw.find(b"\r\n\r\n")
    idx_lf = raw.find(b"\n\n")
    if idx_crlf == -1 and idx_lf == -1:
        head, rest = raw, b""
    elif idx_crlf == -1 or (idx_lf != -1 and idx_lf < idx_crlf):
        head, rest = raw[:idx_lf], raw[idx_lf + 2 :]
    else:
        head, rest = raw[:idx_crlf], raw[idx_crlf + 4 :]
    head_lines = head.replace(b"\r\n", b"\n").split(b"\n")
    # Drop leading DUPLICATE status lines — keep only the last one as the real
    # status (the mini_httpd CGI quirk this module also handles).
    while (
        len(head_lines) >= 2
        and head_lines[0][:5].upper() == b"HTTP/"
        and head_lines[1][:5].upper() == b"HTTP/"
    ):
        head_lines.pop(0)

    status = 0
    if head_lines and head_lines[0][:5].upper() == b"HTTP/":
        parts = head_lines[0].split(None, 2)
        if len(parts) >= 2:
            try:
                status = int(parts[1])
            except ValueError:
                status = 0
        header_lines = head_lines[1:]
    else:
        header_lines = head_lines

    hdrs: dict[str, str] = {}
    set_cookies: list[str] = []
    for line in header_lines:
        if b":" not in line:
            continue
        name, _, value = line.partition(b":")
        key = name.strip().decode("latin-1").lower()
        val = value.strip().decode("latin-1")
        if key == "set-cookie":
            set_cookies.append(val)
        else:
            hdrs[key] = val

    if hdrs.get("transfer-encoding", "").lower() == "chunked":
        rest = _dechunk(rest)
    elif "content-length" in hdrs:
        try:
            rest = rest[: int(hdrs["content-length"])]
        except ValueError:
            pass

    charset = "utf-8"
    ctype = hdrs.get("content-type", "")
    if "charset=" in ctype:
        charset = ctype.split("charset=")[-1].split(";")[0].strip() or "utf-8"
    try:
        text = rest.decode(charset, errors="replace")
    except LookupError:
        text = rest.decode("utf-8", errors="replace")

    return Response(status, text, url, hdrs, set_cookies)


_REDIRECT_STATUSES = {301, 302, 303, 307, 308}


class Fetcher:
    """httpx-first HTTP client that falls back to `raw_fetch` on a protocol
    error, with its own cookie jar and manual redirect following so both paths
    behave identically. Exposes the small surface the credential probe needs."""

    def __init__(
        self,
        timeout: float,
        verify: bool,
        base_headers: dict[str, str],
        connect_timeout: float = 8.0,
    ) -> None:
        self._timeout = timeout  # READ budget (login responses can be delayed)
        self._connect_timeout = min(connect_timeout, timeout)
        self._verify = verify
        self._base = dict(base_headers)
        self.cookies: dict[str, str] = {}
        # Once httpx fails on this host (a crusty server), every later request
        # goes straight to the raw path. This avoids (a) reusing httpx's broken
        # pooled connection and (b) RE-SUBMITTING a login via the httpx-then-raw
        # retry, which would consume the one-time token and a device attempt.
        self._raw_only = False
        # Short connect so dead hosts fail fast; long read so an intentionally
        # throttled login response (anti-bruteforce) is not cut off.
        self._client = httpx.Client(
            timeout=httpx.Timeout(timeout, connect=self._connect_timeout),
            verify=verify,
            follow_redirects=False,
            headers=base_headers,
        )

    def __enter__(self) -> Fetcher:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _cookie_header(self) -> str:
        return "; ".join(f"{k}={v}" for k, v in self.cookies.items())

    def _store_cookies(self, set_cookie_values: list[str]) -> None:
        for sc in set_cookie_values:
            crumb = sc.split(";", 1)[0]
            if "=" in crumb:
                k, v = crumb.split("=", 1)
                self.cookies[k.strip()] = v.strip()

    def _one(
        self, method: str, url: str, body: bytes | None, headers: dict[str, str]
    ) -> Response | None:
        if not self._raw_only:
            try:
                # We manage cookies ourselves (so the httpx and raw paths share
                # one jar); clear httpx's own jar so it doesn't also append
                # Cookie.
                self._client.cookies.clear()
                r = self._client.request(method, url, content=body, headers=headers)
                return Response(
                    r.status_code,
                    r.text,
                    str(r.url),
                    {k.lower(): v for k, v in r.headers.items()},
                    r.headers.get_list("set-cookie"),
                )
            except httpx.HTTPError:
                # This host doesn't work with httpx (malformed responses, broken
                # keep-alive, ...). Switch to the raw path for the REST of the
                # flow so we never retry a submit through httpx again, and CLOSE
                # the httpx client: on tiny embedded servers (mini_httpd) its
                # broken connection otherwise holds one of the few connection
                # slots, so the next raw socket cannot even connect.
                self._raw_only = True
                try:
                    self._client.close()
                except Exception:  # noqa: BLE001 - cleanup must never raise
                    pass

        # Raw path: merge base + per-request headers and parse leniently.
        return raw_fetch(
            method,
            url,
            {**self._base, **headers},
            body,
            self._timeout,
            self._verify,
            connect_timeout=self._connect_timeout,
        )

    def request(
        self,
        method: str,
        url: str,
        *,
        data: dict[str, str] | None = None,
        referer: str | None = None,
        extra_headers: dict[str, str] | None = None,
        max_redirects: int = 5,
    ) -> Response | None:
        cur_method, cur_url, cur_ref = method, url, referer
        body = urlencode(data).encode() if data is not None else None
        for _ in range(max_redirects + 1):
            headers: dict[str, str] = {}
            if cur_ref:
                headers["Referer"] = cur_ref
            if self.cookies:
                headers["Cookie"] = self._cookie_header()
            if extra_headers:
                headers.update(extra_headers)
            resp = self._one(cur_method, cur_url, body, headers)
            if resp is None:
                return None
            self._store_cookies(resp.set_cookies)
            loc = resp.header("location")
            if resp.status_code in _REDIRECT_STATUSES and loc:
                cur_ref = resp.url
                cur_url = urljoin(resp.url, loc)
                if resp.status_code in (301, 302, 303):
                    cur_method, body = "GET", None
                extra_headers = None
                continue
            return resp
        return resp

    def get(
        self,
        url: str,
        *,
        referer: str | None = None,
        basic_auth: tuple[str, str] | None = None,
    ) -> Response | None:
        extra = None
        if basic_auth is not None:
            token = base64.b64encode(f"{basic_auth[0]}:{basic_auth[1]}".encode()).decode()
            extra = {"Authorization": "Basic " + token}
        return self.request("GET", url, referer=referer, extra_headers=extra)

    def post(
        self, url: str, *, data: dict[str, str] | None = None, referer: str | None = None
    ) -> Response | None:
        return self.request("POST", url, data=data, referer=referer)

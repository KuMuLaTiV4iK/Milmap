"""Universal auto-discovery HTTP probe tests (feature 009).

With an empty probe_config the probe must authenticate against any device
without a vendor recipe: HTTP Basic/Digest when challenged, otherwise an
auto-discovered HTML form — carrying hidden per-session tokens, fixed params,
and named submit buttons through verbatim — across the three login shapes
(user+pass together, user-then-pass, password-only). Includes a Grandstream
HT80x simulation mirroring the real `/cgi-bin/dologin` capture.
"""

from __future__ import annotations

import base64
import uuid
from urllib.parse import parse_qs

import httpx

from asset_dashboard.compliance.probes import http as http_probe

AUTO: dict = {}  # empty probe_config -> universal auto-discovery


def _install(monkeypatch, handler, record=None):
    real_client = httpx.Client

    def client_factory(*args, **kwargs):
        if record is not None:
            record["verify"] = kwargs.get("verify")
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(http_probe.httpx, "Client", client_factory)


# --------------------------------------------------------------------------
# Grandstream HT80x simulation (session_token + username + P2 + Login + gnkey)
# --------------------------------------------------------------------------

_STATUS_PAGE = (
    "<html><head><title>Grandstream Device Configuration</title></head><body>"
    "<h1>Grandstream Device Configuration</h1>"
    "STATUS BASIC SETTINGS ADVANCED SETTINGS FXS PORT "
    "MAC Address: 00:0B:82:D7:2C:7B Product Model: HT801 Core Dump: Clean"
    "</body></html>"
)


def _grandstream_login_page(token: str, error: str = "") -> str:
    err = f"<div class='error'>{error}</div>" if error else ""
    return (
        "<html><body><h1>Grandstream Device Configuration</h1>"
        f"{err}"
        "<form method='post' action='/cgi-bin/dologin'>"
        f"<input type='hidden' name='session_token' value='{token}'>"
        "<input type='text' name='username' value=''>"
        "<input type='password' name='P2' value=''>"
        "<input type='submit' name='Login' value='Login'>"
        "<input type='hidden' name='gnkey' value='0b82'>"
        "</form></body></html>"
    )


def _grandstream_handler(record, correct=("user", "123")):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "GET" and path == "/":
            token = uuid.uuid4().hex
            record.setdefault("tokens", []).append(token)
            return httpx.Response(200, html=_grandstream_login_page(token))
        if path == "/cgi-bin/dologin" and request.method == "POST":
            form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
            record.setdefault("posts", []).append(form)
            ok = (
                form.get("username") == correct[0]
                and form.get("P2") == correct[1]
                and form.get("session_token") in record.get("tokens", [])
                and form.get("Login") == "Login"
                and form.get("gnkey") == "0b82"
            )
            if ok:
                return httpx.Response(200, html=_STATUS_PAGE)
            # Rejected: the login form is re-rendered with the error banner.
            return httpx.Response(
                200,
                html=_grandstream_login_page(
                    uuid.uuid4().hex,
                    "Sorry. Your Login Password is not recognized. Remaining Attempts: 1",
                ),
            )
        return httpx.Response(404, html="<html>404 Not Found File not found.</html>")

    return handler


def test_grandstream_auto_accepts_correct_credential(monkeypatch):
    record = {}
    _install(monkeypatch, _grandstream_handler(record))

    result = http_probe.attempt("10.0.0.5", 80, "user", "123", [], probe_config=AUTO)

    assert result.matched is True
    assert result.status == 200
    # The per-session token and fixed fields were carried through verbatim.
    sent = record["posts"][-1]
    assert sent["session_token"] in record["tokens"]
    assert sent["Login"] == "Login" and sent["gnkey"] == "0b82"


def test_grandstream_auto_rejects_wrong_credential(monkeypatch):
    record = {}
    _install(monkeypatch, _grandstream_handler(record))

    result = http_probe.attempt("10.0.0.5", 80, "user", "wrong", [], probe_config=AUTO)

    assert result.matched is False


def test_grandstream_secret_never_in_excerpt(monkeypatch):
    record = {}
    _install(monkeypatch, _grandstream_handler(record))

    result = http_probe.attempt("10.0.0.5", 80, "user", "123", [], probe_config=AUTO)
    assert "123" not in (result.response_excerpt or "")


_GS_404 = (
    "<HTML><HEAD><TITLE>404 Not Found</TITLE></HEAD><BODY>"
    "<H4>404 Not Found</H4> File not found. <HR></BODY></HTML>"
)


def _grandstream_root404_handler(record, correct=("user", "123")):
    """Real HT801 shape: "/" returns the generic 404; the login form is served
    (via GET) at /cgi-bin/dologin and submitted (via POST) to the same path."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/" or path == "/favicon.ico":
            return httpx.Response(404, html=_GS_404)
        if path == "/cgi-bin/dologin" and request.method == "GET":
            token = uuid.uuid4().hex
            record.setdefault("tokens", []).append(token)
            return httpx.Response(200, html=_grandstream_login_page(token))
        if path == "/cgi-bin/dologin" and request.method == "POST":
            form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
            record.setdefault("posts", []).append(form)
            ok = (
                form.get("username") == correct[0]
                and form.get("P2") == correct[1]
                and form.get("session_token") in record.get("tokens", [])
            )
            if ok:
                return httpx.Response(200, html=_STATUS_PAGE)
            return httpx.Response(
                200,
                html=_grandstream_login_page(
                    uuid.uuid4().hex, "Sorry. Your Login Password is not recognized."
                ),
            )
        return httpx.Response(404, html=_GS_404)

    return handler


def test_grandstream_root_404_login_discovered_at_cgi_bin(monkeypatch):
    """Regression: when "/" 404s, discovery must still find the real login page
    and not report the generic 404 as the result for every credential."""
    record = {}
    _install(monkeypatch, _grandstream_root404_handler(record))

    ok = http_probe.attempt("10.0.0.5", 80, "user", "123", [], probe_config=AUTO)
    assert ok.matched is True
    assert ok.status == 200

    bad = http_probe.attempt("10.0.0.5", 80, "user", "wrong", [], probe_config=AUTO)
    assert bad.matched is False
    # The failure is a real rejection, not the generic "File not found" 404.
    assert "404 Not Found" not in (bad.response_excerpt or "")


def test_grandstream_realistic_js_redirect_and_cookie_gated_login(monkeypatch):
    """End-to-end against the real HT801 shape captured from the device:
    GET "/" -> 200 with a JS `window.location` redirect and a Set-Cookie; the
    login form is served at /cgi-bin/login ONLY when that cookie is presented
    (as a browser would), the form's action is the RELATIVE "dologin", and the
    password field is `P2`. Verifies the single-client cookie flow works."""

    SESSION = "sess-abc123"

    def real_login_form(token: str, error: str = "") -> str:
        err = f'<font color="ff0000">{error}</font>' if error else ""
        return (
            "<html><head><title>Grandstream Device Configuration</title></head><body>"
            f"{err}"
            '<form action="dologin" method="post" name="loginOutForm" autocomplete="off">'
            f'<input name="session_token" type=hidden value="{token}">'
            '<input type=text name="username" value="admin" size=30 maxlength=30>'
            '<input name="P2" type=password size=30 maxlength=30>'
            '<input type="submit" name="Login" value="Login">'
            '<input name="gnkey" type=hidden value=0b82>'
            "</form></body></html>"
        )

    record = {}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        has_cookie = request.headers.get("Cookie", "").find(SESSION) != -1
        if path == "/":
            # JS redirect + sets the session cookie the login page needs.
            return httpx.Response(
                200,
                html='<html><head><script language="javascript"><!--\n'
                'window.location = "/cgi-bin/login";\n//--></script>'
                "<title>Grandstream Device Configuration</title></head></html>",
                headers={"Set-Cookie": f"session={SESSION}; path=/"},
            )
        if path == "/cgi-bin/login":
            if not has_cookie:  # cookie-gated: no cookie -> no form (like curl)
                return httpx.Response(200, text="")
            token = uuid.uuid4().hex
            record.setdefault("tokens", []).append(token)
            return httpx.Response(200, html=real_login_form(token))
        if path == "/cgi-bin/dologin" and request.method == "POST":
            form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
            record.setdefault("posts", []).append(form)
            ok = (
                has_cookie
                and form.get("username") == "user"
                and form.get("P2") == "123"
                and form.get("session_token") in record.get("tokens", [])
                and form.get("gnkey") == "0b82"
            )
            if ok:
                return httpx.Response(200, html=_STATUS_PAGE)
            return httpx.Response(
                200,
                html=real_login_form(
                    uuid.uuid4().hex,
                    "Sorry. Your Login Password is not recognized. Remaining Attempts: 1",
                ),
            )
        return httpx.Response(404, html=_GS_404)

    _install(monkeypatch, handler)

    ok = http_probe.attempt("10.0.0.5", 80, "user", "123", [], probe_config=AUTO)
    assert (
        ok.matched is True
    ), f"expected match, got status={ok.status} excerpt={ok.response_excerpt!r}"
    assert ok.status == 200
    # The relative action resolved to /cgi-bin/dologin and carried the token.
    assert record["posts"][-1]["session_token"] in record["tokens"]

    bad = http_probe.attempt("10.0.0.5", 80, "user", "wrong", [], probe_config=AUTO)
    assert bad.matched is False
    # Debuggable: the failure shows the device's rejection text, not a blank.
    assert "not recognized" in (bad.response_excerpt or "").lower()


def test_auto_prefers_complete_form_over_stub_on_root(monkeypatch):
    """Real HT801 shape: "/" embeds a no-JS STUB form (password only, no
    session_token, no username) AND a JS redirect to the complete form at
    /cgi-bin/login. The probe must follow the redirect and submit the complete
    form (with session_token) — submitting the stub fails even for right creds."""
    record = {}

    def complete_form(token: str, error: str = "") -> str:
        err = f'<font color="ff0000">{error}</font>' if error else ""
        return (
            "<html><body>" + err + '<form action="dologin" method="post">'
            f'<input name="session_token" type=hidden value="{token}">'
            '<input type=text name="username" value="admin">'
            '<input name="P2" type=password>'
            '<input type="submit" name="Login" value="Login">'
            '<input name="gnkey" type=hidden value=0b82>'
            "</form></body></html>"
        )

    # The "/" page: a JS redirect plus a STUB form with no token and no username.
    root = (
        '<html><head><script>window.location = "/cgi-bin/login";</script></head>'
        '<body><form action="/cgi-bin/dologin" method="post">'
        '<input name="P2" type=password>'
        '<input type="submit" name="Login" value="Login">'
        '<input name="gnkey" type=hidden value=0b82>'
        "</form></body></html>"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/":
            return httpx.Response(200, html=root)
        if path == "/cgi-bin/login":
            tok = uuid.uuid4().hex
            record.setdefault("tokens", []).append(tok)
            return httpx.Response(200, html=complete_form(tok))
        if path == "/cgi-bin/dologin" and request.method == "POST":
            form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
            # The device REQUIRES the session_token (absent from the stub form).
            if form.get("session_token") not in record.get("tokens", []):
                return httpx.Response(200, html=complete_form(uuid.uuid4().hex, "not recognized"))
            if form.get("username") == "user" and form.get("P2") == "123":
                return httpx.Response(200, html=_STATUS_PAGE)
            return httpx.Response(200, html=complete_form(uuid.uuid4().hex, "not recognized"))
        return httpx.Response(404, html=_GS_404)

    _install(monkeypatch, handler)

    ok = http_probe.attempt("10.0.0.5", 80, "user", "123", [], probe_config=AUTO)
    assert ok.matched is True, f"status={ok.status} excerpt={ok.response_excerpt!r}"
    bad = http_probe.attempt("10.0.0.5", 80, "admin", "admin", [], probe_config=AUTO)
    assert bad.matched is False


def test_auto_sends_referer_for_referer_gated_login_page(monkeypatch):
    """Some Grandstream CGIs serve the login form only when the request carries
    a Referer (as a browser navigating from "/" does). Verify the probe sends
    Referer on the redirect-follow GET and on the POST, and authenticates."""
    seen = {"login_referer": None, "post_referer": None}

    def real_login_form(token: str, error: str = "") -> str:
        err = f'<font color="ff0000">{error}</font>' if error else ""
        return (
            "<html><body>" + err + '<form action="dologin" method="post">'
            f'<input name="session_token" type=hidden value="{token}">'
            '<input type=text name="username" value="admin">'
            '<input name="P2" type=password>'
            '<input type="submit" name="Login" value="Login">'
            '<input name="gnkey" type=hidden value=0b82>'
            "</form></body></html>"
        )

    record = {}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        ref = request.headers.get("Referer")
        if path == "/":
            return httpx.Response(
                200,
                html='<html><head><script>window.location = "/cgi-bin/login";'
                "</script></head></html>",
            )
        if path == "/cgi-bin/login":
            seen["login_referer"] = ref
            if not ref:  # Referer-gated: no Referer -> no form
                return httpx.Response(200, text="")
            token = uuid.uuid4().hex
            record.setdefault("tokens", []).append(token)
            return httpx.Response(200, html=real_login_form(token))
        if path == "/cgi-bin/dologin" and request.method == "POST":
            seen["post_referer"] = ref
            form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
            if (
                form.get("username") == "user"
                and form.get("P2") == "123"
                and form.get("session_token") in record.get("tokens", [])
            ):
                return httpx.Response(200, html=_STATUS_PAGE)
            return httpx.Response(200, html=real_login_form(uuid.uuid4().hex, "not recognized"))
        return httpx.Response(404, html=_GS_404)

    _install(monkeypatch, handler)

    ok = http_probe.attempt("10.0.0.5", 80, "user", "123", [], probe_config=AUTO)
    assert ok.matched is True, f"status={ok.status} excerpt={ok.response_excerpt!r}"
    # Referer points at the root for the login-page GET and at the login page
    # for the POST (port normalization by httpx is not asserted).
    assert seen["login_referer"] and seen["login_referer"].rstrip("/").endswith("10.0.0.5")
    assert seen["post_referer"] and seen["post_referer"].endswith("/cgi-bin/login")


def test_auto_follows_meta_refresh_to_login_page(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/":
            return httpx.Response(
                200,
                html='<html><head><meta http-equiv="refresh" content="0; url=/ui/login">'
                "</head><body>redirecting</body></html>",
            )
        if path == "/ui/login" and request.method == "GET":
            return httpx.Response(
                200,
                html="<form method='post' action='/ui/login'>"
                "<input name='username'><input type='password' name='password'></form>",
            )
        if path == "/ui/login" and request.method == "POST":
            form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
            if (form.get("username"), form.get("password")) == ("admin", "admin"):
                return httpx.Response(200, html="<h1>Welcome admin</h1>")
            return httpx.Response(200, html="<form><input type='password' name='password'></form>")
        return httpx.Response(404)

    _install(monkeypatch, handler)

    assert http_probe.attempt("10.0.0.5", 80, "admin", "admin", [], probe_config=AUTO).matched
    assert not http_probe.attempt("10.0.0.5", 80, "admin", "x", [], probe_config=AUTO).matched


# --------------------------------------------------------------------------
# HTTP Basic via auto-discovery (no probe_config)
# --------------------------------------------------------------------------


def test_auto_handles_basic_auth_when_host_challenges(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        auth = request.headers.get("Authorization")
        if not auth:
            return httpx.Response(401, headers={"WWW-Authenticate": 'Basic realm="x"'})
        user, _, pwd = base64.b64decode(auth.split(" ", 1)[1]).decode().partition(":")
        if (user, pwd) == ("viewer", "viewer"):
            return httpx.Response(200, text="ok")
        return httpx.Response(401, headers={"WWW-Authenticate": 'Basic realm="x"'})

    _install(monkeypatch, handler)

    assert http_probe.attempt("10.0.0.5", 80, "viewer", "viewer", [], probe_config=AUTO).matched
    assert not http_probe.attempt("10.0.0.5", 80, "viewer", "bad", [], probe_config=AUTO).matched


# --------------------------------------------------------------------------
# Password-only form
# --------------------------------------------------------------------------


def test_auto_handles_password_only_form(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                html="<form method='post' action='/login'>"
                "<input type='password' name='pw'></form>",
            )
        form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
        if form.get("pw") == "letmein":
            return httpx.Response(200, html="<h1>Welcome</h1> no form here")
        return httpx.Response(200, html="<form><input type='password' name='pw'></form>")

    _install(monkeypatch, handler)

    assert http_probe.attempt("10.0.0.5", 80, "ignored", "letmein", [], probe_config=AUTO).matched
    assert not http_probe.attempt("10.0.0.5", 80, "ignored", "nope", [], probe_config=AUTO).matched


# --------------------------------------------------------------------------
# Two-step form: username first, password second
# --------------------------------------------------------------------------


def test_auto_handles_two_step_login(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "GET" and path == "/":
            return httpx.Response(
                200,
                html="<form method='post' action='/step2'>"
                "<input type='text' name='username'></form>",
            )
        if path == "/step2":
            form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
            if form.get("username") == "admin":
                return httpx.Response(
                    200,
                    html="<form method='post' action='/step3'>"
                    "<input type='password' name='password'></form>",
                )
            return httpx.Response(200, html="<form><input name='username'></form>")
        if path == "/step3":
            form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
            if form.get("password") == "admin":
                return httpx.Response(200, html="<h1>Dashboard</h1>")
            return httpx.Response(200, html="<form><input type='password' name='password'></form>")
        return httpx.Response(404)

    _install(monkeypatch, handler)

    assert http_probe.attempt("10.0.0.5", 80, "admin", "admin", [], probe_config=AUTO).matched
    assert not http_probe.attempt("10.0.0.5", 80, "admin", "wrong", [], probe_config=AUTO).matched


# --------------------------------------------------------------------------
# No login surface at all
# --------------------------------------------------------------------------


def test_auto_no_form_and_no_challenge_is_not_matched(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, html="<html><body>just a page</body></html>")

    _install(monkeypatch, handler)

    assert not http_probe.attempt("10.0.0.5", 80, "admin", "admin", [], probe_config=AUTO).matched


def test_auto_https_tolerates_self_signed(monkeypatch):
    record = {}
    _install(monkeypatch, _grandstream_handler(record), record)

    http_probe.attempt("10.0.0.5", 443, "user", "123", [], scheme="https", probe_config=AUTO)
    assert record["verify"] is False

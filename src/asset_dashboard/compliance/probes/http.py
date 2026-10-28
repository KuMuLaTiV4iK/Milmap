"""HTTP/HTTPS default-credential probe (local management UIs; FR-036-FR-039).

DEFAULT — universal auto-discovery (feature 009): with an empty
`probe_config` (or `mode: "auto"`), the probe needs no per-vendor recipe. It
fetches the login page and authenticates however the host actually does:

    1. If the host answers with a `WWW-Authenticate` challenge, do HTTP
       Basic or Digest (the native browser-dialog auth of IP phones, cameras,
       switches).
    2. Otherwise discover the HTML login form (see form_discovery.py): resolve
       its action URL, classify the username/password fields, and carry every
       other field — hidden per-session tokens (`session_token`), fixed params
       (`gnkey`), named submit buttons (`Login`) — through verbatim. This
       handles all three login shapes seen in the field: username+password
       together, username-then-password (two-step), and password-only.
    3. Judge generically — no success keywords: a credential is accepted iff
       the response is a normal page that is NOT a re-rendered login form and
       carries no failure phrase ("invalid", "not recognized", ...).

EXPLICIT form config (feature 008) remains for power users / backward
compatibility — any `probe_config` that does not request auto drives the
manual flow below from the dictionary (see data-model.md §1):

    1. GET the login page (fingerprint; also where an optional anti-forgery
       token is captured).
    2. POST (or GET) the credential to the login path, form- or JSON-encoded.
    3. Judge: matched = the response satisfies the configured `success`
       (status in set OR any keyword in body) AND NOT `failure`. With an
       empty `probe_config`, fall back to the legacy keyword rule, but judged
       on the POST response rather than a bare GET.

Feature 009 restores HTTP-auth support for embedded web UIs (IP phones,
cameras, switches) that authenticate with the native browser credential
dialog — `Authorization: Basic`/`Digest` — rather than a form POST. Setting
`probe_config.auth` to "basic", "digest", or "auto" selects this flow:

    1. Send ONE unauthenticated request to the protected path and read the
       `WWW-Authenticate` challenge — i.e. *ask the host which scheme it
       uses* (in "auto" mode; "basic"/"digest" force the scheme).
    2. Re-request the path carrying the credential under the negotiated
       scheme (httpx handles Digest's own challenge/response round-trip).
    3. Judge: accepted iff the host stops challenging (status 2xx/3xx). In
       "auto" mode we additionally require that the first request actually
       demanded auth (401/403/407), so an already-open page is never
       mistaken for a default-credential hit.

HTTPS reuses either flow with `scheme="https"` and `verify=False` so a
self-signed internal cert is tolerated (a local-network accommodation, not
an external fetch — constitution Principle I). The probe still performs
exactly ONE credential attempt per call; the loop/cooldown stays in
compliance/credential_check.py.
"""

from __future__ import annotations

import re
from urllib.parse import urlencode, urljoin

import httpx

from asset_dashboard.compliance.probes import form_discovery
from asset_dashboard.compliance.probes.base import ProbeAttemptResult, body_matches_success
from asset_dashboard.compliance.probes.lenient_http import Fetcher
from asset_dashboard.compliance.probes.lenient_http import Response as LenientResponse

_DEFAULTS = {
    "login_path": "/login",
    "method": "POST",
    "username_field": "username",
    "password_field": "password",
    "encoding": "form",
}

# probe_config.auth values that select the HTTP-auth (Basic/Digest) flow
# instead of the form flow. "auto" negotiates the scheme from the host's
# WWW-Authenticate challenge; the other two force it.
_AUTH_MODES = {"basic", "digest", "auto"}
# Statuses that mean "the host is demanding authentication" (still challenging).
_CHALLENGE_STATUSES = {401, 403, 407}

# Read budget for the universal auto flow. Embedded devices deliberately delay
# the login response as anti-bruteforce throttling (an HT801 took ~14s), so a
# short timeout would cut off a perfectly good response and look like failure.
_AUTO_READ_TIMEOUT = 30.0

# Some embedded UIs serve their login page (and set the session cookie it
# depends on) only to a browser-shaped request. A neutral browser-like
# User-Agent avoids those devices treating the probe as a non-browser client.
_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36 MilmapCredCheck/1.0"
    ),
    # A browser-shaped Accept; some embedded CGIs serve the login HTML only
    # when the request looks like a document navigation.
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Common management-UI login paths, tried in order when the start path ("/")
# serves neither an auth challenge nor a login form — e.g. Grandstream HT80x
# 404s at "/" and serves its form at "/cgi-bin/dologin". This keeps the probe
# vendor-agnostic without a per-device recipe. The first match wins, so the
# list is short and ordered by how common each path is.
_LOGIN_PATH_CANDIDATES = (
    "/",
    "/login",
    "/login.html",
    "/login.htm",
    "/login.asp",
    "/index.html",
    "/index.htm",
    "/index.asp",
    "/cgi-bin/login",
    "/cgi-bin/dologin",
    "/cgi-bin/luci",
    "/cgi-bin/webproc",
    "/admin/",
    "/home.asp",
    "/webLogin.html",
    "/system.html",
)
# After a GET, extract a redirect target the browser would have followed but
# httpx did not: a <meta http-equiv=refresh ... url=...> or a JS location set.
_REDIRECT_HINT_RES = (
    re.compile(r"<meta[^>]+http-equiv=[\"']?refresh[\"']?[^>]+url=([^\"'>\s]+)", re.IGNORECASE),
    re.compile(r"(?:window\.)?location(?:\.href)?\s*=\s*[\"']([^\"']+)[\"']", re.IGNORECASE),
)


def _csrf_from_input(name: str, body: str) -> str | None:
    """A hidden <input name=... value=...> token (either attribute order)."""
    esc = re.escape(name)
    patterns = [
        r"name=[\"']?" + esc + r"[\"']?[^>]*?value=[\"']([^\"']*)[\"']",
        r"value=[\"']([^\"']*)[\"'][^>]*?name=[\"']?" + esc,
    ]
    for pattern in patterns:
        match = re.search(pattern, body, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _csrf_from_meta(name: str, body: str) -> str | None:
    """A <meta name=... content=...> token (either attribute order)."""
    esc = re.escape(name)
    patterns = [
        r"<meta[^>]*?name=[\"']?" + esc + r"[\"']?[^>]*?content=[\"']([^\"']*)[\"']",
        r"<meta[^>]*?content=[\"']([^\"']*)[\"'][^>]*?name=[\"']?" + esc,
    ]
    for pattern in patterns:
        match = re.search(pattern, body, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _csrf_from_script(name: str, body: str) -> str | None:
    """A JS assignment like `session_token = "..."`, `"session_token":"..."`,
    or `session_token='...'` — common when the form is built client-side."""
    esc = re.escape(name)
    match = re.search(esc + r"[\"']?\s*[:=]\s*[\"']([^\"']+)[\"']", body, re.IGNORECASE)
    return match.group(1) if match else None


def _extract_csrf(csrf: dict, resp: httpx.Response) -> str | None:
    """Best-effort anti-forgery / session token capture from the login page.

    `source` selects where to look: "input" (hidden form field, the default),
    "cookie", "header", "meta", "script" (a JS variable), or "auto" to try
    every location in turn. "auto" makes a single config work across the many
    embedded UIs that each stash the token somewhere different (e.g.
    Grandstream HT80x's `session_token`), without needing to know in advance.
    """
    name = csrf.get("name")
    if not name:
        return None
    source = csrf.get("source", "input")
    body = resp.text or ""

    lookups = {
        "cookie": lambda: resp.cookies.get(name),
        "header": lambda: resp.headers.get(name),
        "input": lambda: _csrf_from_input(name, body),
        "meta": lambda: _csrf_from_meta(name, body),
        "script": lambda: _csrf_from_script(name, body),
    }
    if source == "auto":
        # Prefer the explicit form field, then the other carriers.
        order = ["input", "cookie", "meta", "header", "script"]
        for key in order:
            token = lookups[key]()
            if token:
                return token
        return None
    lookup = lookups.get(source, lookups["input"])
    return lookup()


def _negotiate_scheme(
    client: httpx.Client, url: str, forced: str | None
) -> tuple[str | None, bool]:
    """Ask the host which HTTP-auth scheme it wants (feature 009).

    Sends exactly ONE unauthenticated request (no credential submitted, so it
    is not a credential attempt and needs no cooldown) and inspects the
    `WWW-Authenticate` challenge. Returns `(scheme, was_challenged)` where
    `scheme` is the forced scheme when the operator pinned one, else the
    challenge's own scheme ("basic"/"digest") or None if the host offered no
    recognizable challenge; `was_challenged` is True only when the host
    actually demanded authentication, so an open page can't be read as a hit.
    """
    try:
        resp = client.get(url)
    except httpx.HTTPError:
        # Host unreachable for the probe GET: honor a forced scheme, else bail.
        return forced, False
    was_challenged = resp.status_code in _CHALLENGE_STATUSES
    header = resp.headers.get("WWW-Authenticate", "")
    offered = header.strip().split(" ", 1)[0].lower() if header else None
    if forced is not None:
        return forced, was_challenged
    return offered, was_challenged


def _auth_attempt(
    client: httpx.Client, url: str, auth_mode: str, username: str, secret: str
) -> tuple[bool, int | None, str]:
    """One HTTP Basic/Digest credential attempt against `url` (feature 009)."""
    forced = auth_mode if auth_mode in ("basic", "digest") else None
    scheme, was_challenged = _negotiate_scheme(client, url, forced)
    if scheme not in ("basic", "digest"):
        # No scheme to try (auto mode, host offered no known challenge).
        return False, None, ""

    auth = (
        httpx.DigestAuth(username, secret)
        if scheme == "digest"
        else httpx.BasicAuth(username, secret)
    )
    try:
        resp = client.get(url, auth=auth)
    except httpx.HTTPError:
        return False, None, ""

    status = resp.status_code
    body = resp.text or ""
    # Accepted iff the host stopped challenging (2xx/3xx). In negotiated
    # ("auto") mode, also require that it challenged us in the first place so
    # an already-open page is never mistaken for a default-credential match.
    accepted = 200 <= status < 400
    if forced is None:
        accepted = accepted and was_challenged
    return accepted, status, body


def _send_form(
    fetcher: Fetcher,
    method: str,
    url: str,
    payload: dict[str, str],
    referer: str | None = None,
) -> LenientResponse | None:
    if method.lower() == "get":
        query = urlencode(payload)
        full = url + ("&" if "?" in url else "?") + query if query else url
        return fetcher.get(full, referer=referer)
    return fetcher.post(url, data=payload, referer=referer)


def _judge_form_response(resp: LenientResponse) -> tuple[bool, int | None, str]:
    """Generic success test, no per-vendor keywords: a credential is accepted
    iff the response is a normal page (2xx/3xx after following redirects) that
    is NOT a re-rendered login form and carries no failure phrase."""
    status = resp.status_code
    body = resp.text or ""
    if not (200 <= status < 400):
        return False, status, body
    if form_discovery.has_password_input(body):
        return False, status, body
    if form_discovery.has_failure_phrase(body):
        return False, status, body
    # Require POSITIVE evidence: an empty/placeholder body proves nothing, so
    # never treat it as a successful login (guards against a false positive
    # when a response could not be parsed or the device returns a bare 200).
    if not body.strip():
        return False, status, body
    return True, status, body


def _submit_login_form(
    fetcher: Fetcher,
    page_url: str,
    form: form_discovery.Form,
    username: str,
    secret: str,
    *,
    step: int = 0,
) -> tuple[bool, int | None, str]:
    """Submit a discovered login form, transparently handling the three shapes
    the operator described: username+password together, username-then-password
    (two-step), and password-only."""
    action_url = urljoin(page_url, form.action or "")
    payload = form_discovery.build_payload(form, username, secret)
    # A browser submits with the form's own page as Referer; some CGIs require
    # it (the same gate that hides the login page from a bare request).
    referer = page_url

    # Two-step flow: this form asks for the username only (no password field).
    # Submit it, then look for the password form on the next page. Guarded by
    # `step` so we never recurse past the second page.
    if form.password_field() is None and form.username_field() is not None and step == 0:
        resp = _send_form(fetcher, form.method, action_url, payload, referer=referer)
        if resp is None:
            return False, None, ""
        next_form = form_discovery.choose_login_form(form_discovery.parse_forms(resp.text or ""))
        if next_form is not None and next_form.password_field() is not None:
            return _submit_login_form(fetcher, resp.url, next_form, username, secret, step=1)
        return _judge_form_response(resp)

    resp = _send_form(fetcher, form.method, action_url, payload, referer=referer)
    if resp is None:
        return False, None, ""
    return _judge_form_response(resp)


def _is_login_response(resp: LenientResponse | None, *, require_password: bool) -> bool:
    """True if `resp` is a usable login surface: an auth challenge, or a page
    carrying a login form. `require_password` tightens the form test (used when
    brute-probing candidate paths) so a random text form is not mistaken for a
    login; the start path relaxes it to also accept a username-only first step."""
    if resp is None:
        return False
    if resp.status_code in _CHALLENGE_STATUSES:
        return True
    if not (200 <= resp.status_code < 300):
        return False
    form = form_discovery.choose_login_form(form_discovery.parse_forms(resp.text or ""))
    if form is None:
        return False
    if require_password:
        return form.password_field() is not None
    return form.password_field() is not None or form.username_field() is not None


def _get(fetcher: Fetcher, url: str, referer: str | None = None) -> LenientResponse | None:
    return fetcher.get(url, referer=referer)


def _discover_login(
    fetcher: Fetcher, base: str, start_path: str
) -> tuple[LenientResponse | None, LenientResponse | None]:
    """Find the login page without a per-vendor recipe: try the start path,
    then any redirect it hints at, then a short list of common login paths.

    Returns `(login_response, diagnostic_response)`. `login_response` is the
    first response that is an auth challenge or a login form, or None if none
    was found. `diagnostic_response` is the last non-empty response seen (the
    start page, or a candidate) so the caller can still show the operator what
    the device actually answered when no login surface was found."""
    start_url = base + (start_path or "/")
    diag = start = _get(fetcher, start_url)
    if start is not None and start.status_code in _CHALLENGE_STATUSES:
        return start, start

    # If the start page redirects (JS/meta) elsewhere, that target is the REAL
    # login page and MUST be preferred: the start page often embeds only a
    # no-JS *stub* form missing the per-session token (session_token/csrf_token)
    # and even the username field, so submitting it fails even with the right
    # password. A browser never sees that stub — window.location sends it on.
    if start is not None and 200 <= start.status_code < 400:
        body = start.text or ""
        for pattern in _REDIRECT_HINT_RES:
            m = pattern.search(body)
            if m:
                target = urljoin(start.url, m.group(1).strip())
                if target.rstrip("/") != start.url.rstrip("/"):
                    hinted = _get(fetcher, target, referer=start.url)
                    if hinted is not None and hinted.text:
                        diag = hinted
                    if _is_login_response(hinted, require_password=False):
                        return hinted, diag
                break

    # No usable redirect: accept the start page's own login form.
    if _is_login_response(start, require_password=False):
        return start, start

    # Brute a curated candidate list (vendor-agnostic). Require a password
    # field here so we don't latch onto an unrelated text form. Referer is the
    # start URL, matching a browser that reached the candidate from the root.
    for path in _LOGIN_PATH_CANDIDATES:
        if path == start_path:
            continue
        resp = _get(fetcher, base + path, referer=start_url)
        if resp is not None and resp.text:
            diag = resp
        if _is_login_response(resp, require_password=True):
            return resp, diag
    return None, diag


def _auto_attempt(
    fetcher: Fetcher, base: str, login_path: str, username: str, secret: str
) -> tuple[bool, int | None, str]:
    """Universal attempt: discover the login page, then authenticate however the
    host actually does it — HTTP Basic/Digest if it challenges, otherwise the
    auto-discovered HTML login form (feature 009). No vendor recipe required."""
    page, diag = _discover_login(fetcher, base, login_path or "/")
    if page is None:
        # No login surface found. Surface the device's actual answer (status +
        # body) so the operator can debug, instead of a blank result.
        if diag is not None:
            return False, diag.status_code, diag.text or ""
        return False, None, ""

    # Native-dialog auth: the host answered with a WWW-Authenticate challenge.
    if page.status_code in _CHALLENGE_STATUSES:
        header = page.header("www-authenticate")
        scheme = header.strip().split(" ", 1)[0].lower() if header else None
        url = page.url
        if scheme == "basic":
            resp = fetcher.get(url, basic_auth=(username, secret))
            if resp is None:
                return False, None, ""
            return (200 <= resp.status_code < 400), resp.status_code, resp.text or ""
        if scheme == "digest":
            # Digest needs httpx's challenge/response; such servers are
            # standards-compliant (not the mini_httpd quirk), so httpx is fine.
            return _digest_get(url, username, secret)
        return False, page.status_code, page.text or ""

    # Otherwise, discover and submit the HTML login form.
    form = form_discovery.choose_login_form(form_discovery.parse_forms(page.text or ""))
    if form is None:
        return False, page.status_code, page.text or ""
    return _submit_login_form(fetcher, page.url, form, username, secret)


def _digest_get(url: str, username: str, secret: str) -> tuple[bool, int | None, str]:
    """One HTTP Digest GET via httpx (handles the challenge round-trip)."""
    try:
        with httpx.Client(timeout=5.0, follow_redirects=True, headers=_DEFAULT_HEADERS) as client:
            resp = client.get(url, auth=httpx.DigestAuth(username, secret))
        return (200 <= resp.status_code < 400), resp.status_code, resp.text or ""
    except httpx.HTTPError:
        return False, None, ""


def _evaluate(
    status: int | None,
    body: str,
    success: dict | None,
    failure: dict | None,
    success_keywords: list[str],
) -> bool:
    """Success = `success` satisfied AND NOT `failure` (data-model.md §1)."""
    if failure:
        if status is not None and status in (failure.get("status") or []):
            return False
        fkw = failure.get("keywords") or []
        if fkw and body_matches_success(body, fkw):
            return False
    if success:
        sstatus = success.get("status") or []
        skw = success.get("keywords") or []
        if sstatus or skw:
            matched = (status is not None and status in sstatus) or (
                bool(skw) and body_matches_success(body, skw)
            )
            return matched
    # Empty/under-specified probe_config: legacy keyword rule on the POST body.
    return body_matches_success(body, success_keywords)


def attempt(
    host: str,
    port: int,
    username: str,
    secret: str,
    success_keywords: list[str],
    timeout: float = 5.0,
    scheme: str = "http",
    probe_config: dict | None = None,
) -> ProbeAttemptResult:
    raw = probe_config or {}
    cfg = {**_DEFAULTS, **raw}
    login_path = cfg["login_path"]
    # The credential is SUBMITTED to `action` (defaults to `login_path`). Some
    # firmwares serve the login *page* at one URL and accept the POST at
    # another — e.g. Grandstream HT80x shows the form at "/" but submits to
    # "/cgi-bin/dologin" — so the GET (fingerprint/cookie/CSRF) and the POST
    # target are configured independently.
    action_path = cfg.get("action") or login_path
    method = str(cfg["method"]).upper()
    encoding = cfg["encoding"]
    auth_mode = str(cfg.get("auth") or "").lower()
    mode = str(cfg.get("mode") or "").lower()
    # Some login flows answer a successful POST with a redirect to the
    # authenticated page; following it lets the body-keyword success check see
    # that page. Off by default to preserve existing status-based configs.
    follow_redirects = bool(cfg.get("follow_redirects", False))
    base = f"{scheme}://{host}:{port}"
    # Self-signed TLS is tolerated on internal HTTPS management UIs.
    verify = scheme != "https"

    # Feature 009: HTTP Basic/Digest flow for native-dialog auth (IP phones,
    # cameras, switches). `auth_path` falls back to `login_path` so a single
    # field configures the protected resource (commonly "/").
    if auth_mode in _AUTH_MODES:
        auth_url = base + (cfg.get("auth_path") or login_path)
        with httpx.Client(
            timeout=timeout, verify=verify, follow_redirects=False, headers=_DEFAULT_HEADERS
        ) as client:
            matched, status, body = _auth_attempt(client, auth_url, auth_mode, username, secret)
        return ProbeAttemptResult(matched=matched, response_excerpt=body[:200], status=status)

    # Universal auto-discovery is the default: it runs when no probe_config was
    # supplied, or when `mode: "auto"` is set. It fetches the login page and
    # authenticates however the host actually does (Basic/Digest or a
    # discovered HTML form), so no per-vendor recipe is needed. An explicit
    # form config (any probe_config without `mode: "auto"`) keeps the manual
    # flow below for power users and backward compatibility.
    use_auto = mode == "auto" or (not raw)
    if use_auto:
        auto_login_path = cfg.get("login_path") if "login_path" in raw else "/"
        # Fetcher uses httpx normally but falls back to a lenient raw-socket
        # parser for crusty embedded servers (e.g. mini_httpd's doubled status
        # line) that h11 rejects outright. The read budget is generous because
        # these devices THROTTLE the login response (anti-bruteforce) — an
        # HT801 took ~14s — while the connect stays short so dead hosts fail
        # fast.
        read_timeout = max(timeout, _AUTO_READ_TIMEOUT)
        with Fetcher(read_timeout, verify, _DEFAULT_HEADERS) as fetcher:
            matched, status, body = _auto_attempt(
                fetcher, base, auto_login_path or "/", username, secret
            )
        return ProbeAttemptResult(matched=matched, response_excerpt=body[:200], status=status)

    status: int | None = None
    body = ""
    try:
        with httpx.Client(
            timeout=timeout,
            verify=verify,
            follow_redirects=follow_redirects,
            headers=_DEFAULT_HEADERS,
        ) as client:
            # Step 1: GET the login page (fingerprint + cookie + CSRF capture).
            form: dict[str, str] = dict(cfg.get("extra_fields") or {})
            csrf = cfg.get("csrf")
            try:
                page = client.get(base + login_path)
                if isinstance(csrf, dict):
                    token = _extract_csrf(csrf, page)
                    if token is not None:
                        form[csrf.get("field") or csrf.get("name")] = token
            except httpx.HTTPError:
                page = None  # keep going — some endpoints have no GET page

            # Step 2: submit the credential to the form action.
            form[cfg["username_field"]] = username
            form[cfg["password_field"]] = secret
            if method == "GET":
                resp = client.get(base + action_path, params=form)
            elif encoding == "json":
                resp = client.post(base + action_path, json=form)
            else:
                resp = client.post(base + action_path, data=form)
            status = resp.status_code
            body = resp.text or ""
    except httpx.HTTPError:
        status = None
        body = ""

    matched = _evaluate(status, body, cfg.get("success"), cfg.get("failure"), success_keywords)
    return ProbeAttemptResult(matched=matched, response_excerpt=body[:200], status=status)

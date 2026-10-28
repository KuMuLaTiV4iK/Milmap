"""HTTP/HTTPS default-credential probe (local management UIs; FR-036-FR-039).

Feature 008 replaces the old Basic-auth `GET /` probe — which never
authenticated against a form login — with a form-aware flow driven by the
dictionary's `probe_config` (see data-model.md §1):

    1. GET the login page (fingerprint; also where an optional anti-forgery
       token is captured).
    2. POST (or GET) the credential to the login path, form- or JSON-encoded.
    3. Judge: matched = the response satisfies the configured `success`
       (status in set OR any keyword in body) AND NOT `failure`. With an
       empty `probe_config`, fall back to the legacy keyword rule, but judged
       on the POST response rather than a bare GET.

HTTPS reuses this flow with `scheme="https"` and `verify=False` so a
self-signed internal cert is tolerated (a local-network accommodation, not
an external fetch — constitution Principle I). The probe still performs
exactly ONE authentication attempt per call; the loop/cooldown stays in
compliance/credential_check.py.
"""

from __future__ import annotations

import re

import httpx

from asset_dashboard.compliance.probes.base import ProbeAttemptResult, body_matches_success

_DEFAULTS = {
    "login_path": "/login",
    "method": "POST",
    "username_field": "username",
    "password_field": "password",
    "encoding": "form",
}


def _extract_csrf(csrf: dict, resp: httpx.Response) -> str | None:
    """Best-effort anti-forgery token capture from the login-page response."""
    name = csrf.get("name")
    if not name:
        return None
    source = csrf.get("source", "input")
    if source == "cookie":
        return resp.cookies.get(name)
    if source == "header":
        return resp.headers.get(name)
    # Default: a hidden <input name=... value=...> on the login page. Try both
    # attribute orders; the value is body-derived HTML, never a secret.
    body = resp.text or ""
    patterns = [
        r"name=[\"']?" + re.escape(name) + r"[\"']?[^>]*?value=[\"']([^\"']*)[\"']",
        r"value=[\"']([^\"']*)[\"'][^>]*?name=[\"']?" + re.escape(name),
    ]
    for pattern in patterns:
        match = re.search(pattern, body, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


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
    cfg = {**_DEFAULTS, **(probe_config or {})}
    login_path = cfg["login_path"]
    method = str(cfg["method"]).upper()
    encoding = cfg["encoding"]
    base = f"{scheme}://{host}:{port}"
    # Self-signed TLS is tolerated on internal HTTPS management UIs.
    verify = scheme != "https"

    status: int | None = None
    body = ""
    try:
        with httpx.Client(timeout=timeout, verify=verify, follow_redirects=False) as client:
            # Step 1: GET the login page (fingerprint + CSRF capture).
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

            # Step 2: submit the credential.
            form[cfg["username_field"]] = username
            form[cfg["password_field"]] = secret
            if method == "GET":
                resp = client.get(base + login_path, params=form)
            elif encoding == "json":
                resp = client.post(base + login_path, json=form)
            else:
                resp = client.post(base + login_path, data=form)
            status = resp.status_code
            body = resp.text or ""
    except httpx.HTTPError:
        status = None
        body = ""

    matched = _evaluate(status, body, cfg.get("success"), cfg.get("failure"), success_keywords)
    return ProbeAttemptResult(matched=matched, response_excerpt=body[:200], status=status)

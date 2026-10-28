"""Universal HTML login-form discovery for the HTTP/HTTPS credential probe.

The credential check must work against *any* embedded management UI without a
vendor-specific recipe in the dictionary (feature 009). Given a login page's
HTML, this module finds the login form, classifies its username/password
fields, and carries every other field (hidden tokens like `session_token`,
fixed params like `gnkey`, and named submit buttons like `Login`) through to
the POST verbatim — so per-session tokens and vendor quirks are handled
automatically rather than configured.

Parsing uses only the standard library's `html.parser` (no third-party
dependency, so it runs in the air-gapped target environment).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

# A field is the password field if its type is `password`, or (for the rare
# form that mistypes it) its name looks like one. `p2` is Grandstream's.
_PASSWORD_NAME_RE = re.compile(r"(pass|pwd|passwd|secret|^p2$)", re.IGNORECASE)
# A field is the username field if it is a visible text input whose name looks
# like an identity field; else the first visible text input is used.
_USERNAME_NAME_RE = re.compile(r"(user|login|logon|uid|account|email|name)", re.IGNORECASE)
# Visible text-like input types that can carry a username.
_TEXTY_TYPES = {"", "text", "email", "tel", "search", None}
# Phrases that mean "authentication did not succeed" on a re-rendered page.
_FAILURE_PHRASES = (
    "incorrect",
    "invalid",
    "not recognized",
    "login failed",
    "authentication failed",
    "access denied",
    "permission denied",
    "wrong password",
    "wrong username",
    "bad password",
    "try again",
    "unauthorized",
    "login error",
    "sorry",
)


@dataclass
class FormField:
    name: str
    type: str
    value: str = ""


@dataclass
class Form:
    action: str | None = None
    method: str = "get"
    fields: list[FormField] = field(default_factory=list)

    def password_field(self) -> FormField | None:
        for f in self.fields:
            if (f.type or "").lower() == "password":
                return f
        for f in self.fields:
            if (f.type or "").lower() not in ("hidden", "submit", "button") and (
                f.name and _PASSWORD_NAME_RE.search(f.name)
            ):
                return f
        return None

    def username_field(self) -> FormField | None:
        pw = self.password_field()
        candidates = [
            f
            for f in self.fields
            if f is not pw and (f.type or "").lower() in _TEXTY_TYPES and f.name
        ]
        for f in candidates:
            if _USERNAME_NAME_RE.search(f.name):
                return f
        return candidates[0] if candidates else None


class _FormCollector(HTMLParser):
    """Collects every <form> and the named controls nested inside it."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.forms: list[Form] = []
        self._current: Form | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "form":
            self._current = Form(
                action=a.get("action"),
                method=(a.get("method") or "get").lower(),
            )
            self.forms.append(self._current)
        elif tag in ("input", "button", "select", "textarea") and self._current is not None:
            name = a.get("name")
            if not name:
                return
            ftype = a.get("type", "text" if tag != "button" else "submit")
            self._current.fields.append(FormField(name=name, type=ftype, value=a.get("value", "")))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag == "form":
            self._current = None


def parse_forms(html: str) -> list[Form]:
    parser = _FormCollector()
    try:
        parser.feed(html or "")
    except Exception:
        # Malformed markup must never crash a probe; return what we gathered.
        pass
    return parser.forms


def choose_login_form(forms: list[Form]) -> Form | None:
    """Pick the most login-like form: one with a password field wins; failing
    that, the first form carrying a visible text (username) field."""
    for f in forms:
        if f.password_field() is not None:
            return f
    for f in forms:
        if f.username_field() is not None:
            return f
    return None


def build_payload(form: Form, username: str, secret: str) -> dict[str, str]:
    """Build the POST/GET body: carry every named field verbatim, then set the
    discovered username/password fields to the candidate credential."""
    payload: dict[str, str] = {}
    for f in form.fields:
        # Named submit buttons (e.g. Login=Login) and hidden tokens must be
        # sent as the browser would; default other fields to their value.
        payload[f.name] = f.value or ""
    uf = form.username_field()
    pf = form.password_field()
    if uf is not None:
        payload[uf.name] = username
    if pf is not None:
        payload[pf.name] = secret
    return payload


def has_password_input(html: str) -> bool:
    """True if the (response) HTML still shows a password input — i.e. we are
    looking at a login form again, the hallmark of a rejected attempt."""
    form = choose_login_form(parse_forms(html))
    return form is not None and form.password_field() is not None


def has_failure_phrase(html: str) -> bool:
    lowered = (html or "").lower()
    return any(phrase in lowered for phrase in _FAILURE_PHRASES)

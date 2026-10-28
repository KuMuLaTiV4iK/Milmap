"""SIP default-credential probe (VoIP endpoints, ports 5060-5062; FR-036-FR-039).

Performs a real two-step SIP Digest authentication exchange (RFC 3261 /
RFC 2617): an initial unauthenticated REGISTER, a 401/407 challenge
carrying `realm`/`nonce` (and, on most real servers, `qop="auth"`), then
a second REGISTER with a properly computed MD5 digest response — using
the qop-aware formula when the server offers `qop=auth` (the common
case; e.g. Asterisk sends this by default) and falling back to the
legacy RFC 2069-compatible formula when no `qop` is offered. A server
that still accepts a known default credential will answer the second
REGISTER with 200 OK; the confirmation itself is a response-BODY
keyword match (FR-036a), not merely that status code.

One full exchange (two UDP round-trips) per call — the orchestrator
(credential_check.py) is solely responsible for how many times this is
called and how far apart (the device-safety invariants); this function
has no retry logic of its own.
"""

from __future__ import annotations

import hashlib
import re
import secrets
import socket

from asset_dashboard.compliance.probes.base import ProbeAttemptResult, body_matches_success

_CALL_ID = "asset-dashboard-compliance-audit"
_METHOD = "REGISTER"
_NC = "00000001"

_REGISTER_NO_AUTH = (
    "REGISTER sip:{host} SIP/2.0\r\n"
    "Via: SIP/2.0/UDP 0.0.0.0:5060;branch=z9hG4bK-audit1\r\n"
    "Max-Forwards: 70\r\n"
    "To: <sip:{username}@{host}>\r\n"
    "From: <sip:{username}@{host}>;tag=audit\r\n"
    "Call-ID: {call_id}\r\n"
    "CSeq: 1 REGISTER\r\n"
    "Contact: <sip:{username}@0.0.0.0:5060>\r\n"
    "Content-Length: 0\r\n\r\n"
)

# Used both for the qop=auth case (adds qop/nc/cnonce) and the legacy
# no-qop case (that block is omitted via the {qop_block} placeholder).
_REGISTER_WITH_AUTH = (
    "REGISTER sip:{host} SIP/2.0\r\n"
    "Via: SIP/2.0/UDP 0.0.0.0:5060;branch=z9hG4bK-audit2\r\n"
    "Max-Forwards: 70\r\n"
    "To: <sip:{username}@{host}>\r\n"
    "From: <sip:{username}@{host}>;tag=audit\r\n"
    "Call-ID: {call_id}\r\n"
    "CSeq: 2 REGISTER\r\n"
    "Contact: <sip:{username}@0.0.0.0:5060>\r\n"
    'Authorization: Digest username="{username}", realm="{realm}", nonce="{nonce}", '
    'uri="sip:{host}", response="{digest_response}", algorithm=MD5{qop_block}\r\n'
    "Content-Length: 0\r\n\r\n"
)

_CHALLENGE_RE = re.compile(
    r"(?:WWW-Authenticate|Proxy-Authenticate):\s*Digest\s+(?P<params>[^\r\n]+)", re.IGNORECASE
)


def _parse_digest_params(header_value: str) -> dict[str, str]:
    """Parse comma-separated `key="value"` / `key=value` pairs.

    A quoted value may itself contain a comma (e.g. `qop="auth,auth-int"`),
    so quoted and unquoted values are matched with distinct alternatives
    rather than a single character class that would stop at the first comma.
    """
    params: dict[str, str] = {}
    pattern = r'(\w+)=(?:"([^"]*)"|([^,\s]+))'
    for match in re.finditer(pattern, header_value):
        key = match.group(1).lower()
        value = match.group(2) if match.group(2) is not None else match.group(3)
        params[key] = value
    return params


def _compute_digest_response(
    username: str,
    realm: str,
    secret: str,
    nonce: str,
    method: str,
    uri: str,
    *,
    qop: str | None = None,
    nc: str = _NC,
    cnonce: str = "",
) -> str:
    """RFC 2617 MD5 digest.

    qop="auth":  response = MD5(HA1:nonce:nc:cnonce:qop:HA2)  (§3.2.2.1)
    qop=None:    response = MD5(HA1:nonce:HA2)                 (RFC 2069 compatibility)
    """
    ha1 = hashlib.md5(f"{username}:{realm}:{secret}".encode()).hexdigest()  # noqa: S324 - SIP digest requires MD5
    ha2 = hashlib.md5(f"{method}:{uri}".encode()).hexdigest()  # noqa: S324
    if qop:
        return hashlib.md5(f"{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}".encode()).hexdigest()  # noqa: S324
    return hashlib.md5(f"{ha1}:{nonce}:{ha2}".encode()).hexdigest()  # noqa: S324


def attempt(
    host: str,
    port: int,
    username: str,
    secret: str,
    success_keywords: list[str],
    timeout: float = 3.0,
) -> ProbeAttemptResult:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        # Step 1: unauthenticated REGISTER, expect a digest challenge.
        first_message = _REGISTER_NO_AUTH.format(host=host, username=username, call_id=_CALL_ID)
        sock.sendto(first_message.encode(), (host, port))
        first_data, _ = sock.recvfrom(4096)
        first_body = first_data.decode(errors="replace")

        challenge = _CHALLENGE_RE.search(first_body)
        if not challenge:
            # No challenge offered (e.g. no auth required, or an
            # unexpected reply) — nothing to confirm acceptance with via
            # a proper exchange; fall back to matching this first reply
            # directly, but never treat a bare status code as success.
            return ProbeAttemptResult(
                matched=body_matches_success(first_body, success_keywords),
                response_excerpt=first_body[:200],
            )

        params = _parse_digest_params(challenge.group("params"))
        realm, nonce = params.get("realm", ""), params.get("nonce", "")
        uri = f"sip:{host}"

        # Prefer qop="auth" when offered (the common case on real
        # servers); "auth-int" is not supported (it hashes a message
        # body our bodiless REGISTER doesn't have), so fall back to the
        # legacy no-qop formula if only auth-int is on offer.
        offered_qop = params.get("qop", "")
        use_qop = "auth" if "auth" in [q.strip() for q in offered_qop.split(",")] else None
        cnonce = secrets.token_hex(8) if use_qop else ""

        digest_response = _compute_digest_response(
            username, realm, secret, nonce, _METHOD, uri, qop=use_qop, nc=_NC, cnonce=cnonce
        )
        qop_block = f', qop={use_qop}, nc={_NC}, cnonce="{cnonce}"' if use_qop else ""

        # Step 2: REGISTER with the computed digest response.
        second_message = _REGISTER_WITH_AUTH.format(
            host=host,
            username=username,
            call_id=_CALL_ID,
            realm=realm,
            nonce=nonce,
            digest_response=digest_response,
            qop_block=qop_block,
        )
        sock.sendto(second_message.encode(), (host, port))
        second_data, _ = sock.recvfrom(4096)
        second_body = second_data.decode(errors="replace")
    except OSError:
        return ProbeAttemptResult(matched=False, response_excerpt="")  # unreachable/timeout
    finally:
        sock.close()

    return ProbeAttemptResult(
        matched=body_matches_success(second_body, success_keywords),
        response_excerpt=second_body[:200],
    )

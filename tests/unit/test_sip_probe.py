"""Unit tests for the SIP probe's RFC 2617 digest computation.

`test_digest_response_matches_rfc2617_qop_auth_worked_example` is pinned
to the AUTHORITATIVE worked example in RFC 2617 §3.5 itself (fetched and
read directly from the RFC text, not recalled from memory) — including
its `qop="auth"` challenge, which uses the formula
response = MD5(HA1:nonce:nc:cnonce:qop:HA2), distinct from the simpler
legacy (no-qop) formula also covered below.
"""
from asset_dashboard.compliance.probes.sip import _compute_digest_response, _parse_digest_params


def test_digest_response_matches_rfc2617_qop_auth_worked_example():
    # RFC 2617 §3.5: challenge realm="testrealm@host.com",
    # nonce="dcd98b7102dd2f0e8b11d0f600bfb0c093"; client response uses
    # qop=auth, nc=00000001, cnonce="0a4f113b" against
    # GET /dir/index.html with username "Mufasa" / password "Circle Of Life".
    response = _compute_digest_response(
        username="Mufasa",
        realm="testrealm@host.com",
        secret="Circle Of Life",
        nonce="dcd98b7102dd2f0e8b11d0f600bfb0c093",
        method="GET",
        uri="/dir/index.html",
        qop="auth",
        nc="00000001",
        cnonce="0a4f113b",
    )
    assert response == "6629fae49393a05397450978507c4ef1"


def test_legacy_no_qop_formula_differs_from_qop_auth_formula():
    # Same inputs, but without qop — RFC 2069-compatible legacy formula.
    # It is a DIFFERENT computation (no nc/cnonce/qop folded in), so it
    # must not coincidentally match the qop=auth result above.
    legacy_response = _compute_digest_response(
        username="Mufasa",
        realm="testrealm@host.com",
        secret="Circle Of Life",
        nonce="dcd98b7102dd2f0e8b11d0f600bfb0c093",
        method="GET",
        uri="/dir/index.html",
    )
    assert legacy_response != "6629fae49393a05397450978507c4ef1"


def test_parse_digest_params_extracts_realm_nonce_and_qop():
    header = 'realm="voip.example", qop="auth,auth-int", nonce="abc123", algorithm=MD5'
    params = _parse_digest_params(header)
    assert params["realm"] == "voip.example"
    assert params["nonce"] == "abc123"
    assert params["qop"] == "auth,auth-int"


def test_wrong_secret_produces_a_different_digest():
    args = ("admin", "realm", "admin", "nonce1", "REGISTER", "sip:host")
    wrong_args = ("admin", "realm", "wrong-password", "nonce1", "REGISTER", "sip:host")
    assert _compute_digest_response(*args) != _compute_digest_response(*wrong_args)

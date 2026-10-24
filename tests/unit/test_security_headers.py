"""Security response headers are present on every response, including
gated/unauthenticated ones (defense in depth around the auth gate)."""


def test_security_headers_present_on_authenticated_response(authed_client):
    resp = authed_client.get("/profiles")
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"
    assert resp.headers["referrer-policy"] == "no-referrer"
    assert "default-src 'self'" in resp.headers["content-security-policy"]


def test_security_headers_present_on_unauthenticated_401(client):
    resp = client.get("/api/profiles")
    assert resp.status_code == 401
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"

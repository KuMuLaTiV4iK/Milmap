"""Shared JSON error shape and CSRF protection for state-changing requests.

Error shape (contracts/http-api.md):
    { "error": { "code": str, "message": str, "fields"?: {field: message} } }
"""
from __future__ import annotations

import hmac
import secrets

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "x-csrf-token"


def api_error(code: str, message: str, *, fields: dict[str, str] | None = None) -> dict:
    body: dict = {"error": {"code": code, "message": message}}
    if fields:
        body["error"]["fields"] = fields
    return body


def validation_error(fields: dict[str, str]) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=api_error("validation_error", "One or more fields are invalid.", fields=fields),
    )


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def verify_csrf(request: Request) -> None:
    """Raise 403 unless the request's CSRF header matches its session cookie.

    Applies to all state-changing (POST/PUT/DELETE) JSON/form requests.
    """
    cookie_value = request.cookies.get(CSRF_COOKIE_NAME)
    header_value = request.headers.get(CSRF_HEADER_NAME)
    if not cookie_value or not header_value or not hmac.compare_digest(cookie_value, header_value):
        raise HTTPException(
            status_code=403,
            detail=api_error("csrf_invalid", "Missing or invalid CSRF token."),
        )

"""Server-side sessions + the auth-gate middleware (FR-001, FR-005).

Sessions are kept server-side (not JWT) so idle-timeout and revocation are
simple and immediate. The session id itself is an opaque, signed cookie
value; session state (username, last-seen time) lives in a server-side
store, not in the cookie.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock

from fastapi import Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from itsdangerous import BadSignature, URLSafeSerializer
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from asset_dashboard.config import settings
from asset_dashboard.web.errors import CSRF_COOKIE_NAME, api_error, generate_csrf_token

SESSION_COOKIE_NAME = "session_id"
_SECRET_KEY_PATH_NOTE = (
    "A production deployment MUST load this from a locally-generated secret file, "
    "not a hardcoded value. See data/secret_key (generated on first run)."
)

# Paths reachable without an authenticated session (FR-001).
_PUBLIC_PATHS = {"/login", "/api/auth/login"}
_PUBLIC_PREFIXES = ("/static/",)


@dataclass
class _SessionRecord:
    username: str
    last_seen: float


class SessionStore:
    """In-memory, server-side session store with idle-timeout eviction."""

    def __init__(self, idle_timeout_seconds: int, secret_key: str | None = None) -> None:
        self._idle_timeout = idle_timeout_seconds
        self._sessions: dict[str, _SessionRecord] = {}
        self._lock = Lock()
        # `secret_key` is injectable so tests never read/create the real
        # on-disk key (and never share session state across test runs);
        # production code always goes through the on-disk default.
        self._serializer = URLSafeSerializer(secret_key or _load_or_create_secret_key())

    def create(self, username: str) -> str:
        session_id = self._serializer.dumps({"u": username, "n": time.time()})
        with self._lock:
            self._sessions[session_id] = _SessionRecord(username=username, last_seen=time.time())
        return session_id

    def touch_and_get(
        self, session_id: str | None, *, idle_timeout_seconds: int | None = None
    ) -> str | None:
        """Return the username for a valid, non-expired session, bumping last_seen.

        `idle_timeout_seconds` lets a caller pass the *effective* (admin-
        editable, FR-032) setting; falls back to the value this store was
        constructed with when omitted.
        """
        if not session_id:
            return None
        try:
            self._serializer.loads(session_id)
        except BadSignature:
            return None
        idle_timeout = (
            idle_timeout_seconds if idle_timeout_seconds is not None else self._idle_timeout
        )
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            if time.time() - record.last_seen > idle_timeout:
                del self._sessions[session_id]
                return None
            record.last_seen = time.time()
            return record.username

    def destroy(self, session_id: str | None) -> None:
        if not session_id:
            return
        with self._lock:
            self._sessions.pop(session_id, None)

    def destroy_for_username(self, username: str) -> None:
        """Invalidate every live session for `username` (FR-034): an admin
        deactivating or resetting a user's password ends their session at
        their next action, not merely blocking future sign-ins."""
        with self._lock:
            stale = [sid for sid, rec in self._sessions.items() if rec.username == username]
            for sid in stale:
                del self._sessions[sid]


def _load_or_create_secret_key() -> str:
    from asset_dashboard.config import DATA_DIR

    key_path = DATA_DIR / "secret_key"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if key_path.exists():
        return key_path.read_text().strip()
    import secrets as _secrets

    key = _secrets.token_urlsafe(48)
    key_path.write_text(key)
    return key


session_store = SessionStore(idle_timeout_seconds=settings.session_idle_timeout_seconds)


def _is_public(path: str) -> bool:
    return path in _PUBLIC_PATHS or any(path.startswith(p) for p in _PUBLIC_PREFIXES)


def _wants_json(request: Request) -> bool:
    return request.url.path.startswith("/api/") or "application/json" in request.headers.get(
        "accept", ""
    )


class AuthGateMiddleware(BaseHTTPMiddleware):
    """Blocks every request to a non-public path unless it carries a valid session.

    No page, data, or action is reachable without authentication (FR-001):
    an unauthenticated JSON/API request gets 401 with no data disclosed; an
    unauthenticated HTML request is redirected to /login.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    @staticmethod
    def _effective_idle_timeout() -> int:
        from asset_dashboard.db.base import session_scope  # noqa: PLC0415
        from asset_dashboard.settings_store.service import get_effective_value  # noqa: PLC0415

        try:
            with session_scope() as db_session:
                return get_effective_value(db_session, "session_idle_timeout_seconds")
        except Exception:  # noqa: BLE001 - DB unavailable; fall back to the construction-time default
            return settings.session_idle_timeout_seconds

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if _is_public(request.url.path):
            return await call_next(request)

        session_id = request.cookies.get(SESSION_COOKIE_NAME)
        idle_timeout = self._effective_idle_timeout()
        username = session_store.touch_and_get(session_id, idle_timeout_seconds=idle_timeout)

        if username is None:
            if _wants_json(request):
                return JSONResponse(
                    status_code=401,
                    content=api_error("unauthenticated", "Sign-in required."),
                )
            return RedirectResponse(url="/login", status_code=303)

        request.state.user = username
        return await call_next(request)


def set_session_cookies(response: Response, session_id: str) -> None:
    """Set the session cookie and a fresh CSRF cookie together on successful sign-in."""
    response.set_cookie(
        SESSION_COOKIE_NAME,
        session_id,
        httponly=True,
        samesite="lax",
        secure=False,  # local-only air-gapped deployment; set True if TLS is terminated
    )
    response.set_cookie(
        CSRF_COOKIE_NAME,
        generate_csrf_token(),
        httponly=False,  # must be readable by the page to echo back in the header
        samesite="lax",
        secure=False,
    )


def clear_session_cookies(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME)
    response.delete_cookie(CSRF_COOKIE_NAME)

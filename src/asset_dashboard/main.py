"""ASGI app factory and Uvicorn entry point.

Run locally (air-gapped host, no external interfaces):

    python -m asset_dashboard.main
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.staticfiles import StaticFiles

from asset_dashboard.auth.sessions import AuthGateMiddleware
from asset_dashboard.web.security_headers import SecurityHeadersMiddleware

STATIC_DIR = Path(__file__).parent / "web" / "static"
TEMPLATES_DIR = Path(__file__).parent / "web" / "templates"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown hooks — starts/stops the scheduling heartbeat (US5)."""
    from asset_dashboard.scheduling.engine import shutdown_scheduler, start_scheduler

    start_scheduler()
    yield
    shutdown_scheduler()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Asset Inventory & Compliance Management Dashboard",
        lifespan=lifespan,
    )
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.add_middleware(AuthGateMiddleware)
    # Added after the auth gate so it wraps it (outermost) — security
    # headers apply to every response, including 401s and the /login redirect.
    app.add_middleware(SecurityHeadersMiddleware)

    @app.exception_handler(HTTPException)
    async def _api_shaped_http_exception_handler(request: Request, exc: HTTPException):
        # Dependencies (auth/authz.py, web/errors.verify_csrf) raise HTTPException
        # with `detail` already shaped as {"error": {...}} (web/errors.api_error) —
        # return that shape directly rather than FastAPI's default {"detail": ...}
        # wrapping, so every error response follows the one contract shape.
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=exc.status_code, content=exc.detail, headers=exc.headers
            )
        return await http_exception_handler(request, exc)

    # Routers are included as each user-story module implements them.
    from asset_dashboard.auth.routes import router as auth_router  # noqa: PLC0415
    from asset_dashboard.auth.routes_users import router as users_router  # noqa: PLC0415
    from asset_dashboard.discovery.routes import pages_router as discovery_pages_router  # noqa: PLC0415
    from asset_dashboard.discovery.routes import router as discovery_router  # noqa: PLC0415
    from asset_dashboard.history.routes import pages_router as history_pages_router  # noqa: PLC0415
    from asset_dashboard.history.routes import router as history_router  # noqa: PLC0415
    from asset_dashboard.nse.routes import router as nse_router  # noqa: PLC0415
    from asset_dashboard.profiles.routes import pages_router as profiles_pages_router  # noqa: PLC0415
    from asset_dashboard.profiles.routes import router as profiles_router  # noqa: PLC0415
    from asset_dashboard.reference_versions.routes import (
        pages_router as reference_versions_pages_router,  # noqa: PLC0415
    )
    from asset_dashboard.reference_versions.routes import router as reference_versions_router  # noqa: PLC0415
    from asset_dashboard.scheduling.routes import pages_router as scheduling_pages_router  # noqa: PLC0415
    from asset_dashboard.scheduling.routes import router as scheduling_router  # noqa: PLC0415
    from asset_dashboard.settings_store.routes import pages_router as settings_pages_router  # noqa: PLC0415
    from asset_dashboard.settings_store.routes import router as settings_router  # noqa: PLC0415
    from asset_dashboard.tools.credential_tool.routes import pages_router as tool_pages_router  # noqa: PLC0415
    from asset_dashboard.tools.credential_tool.routes import router as tool_router  # noqa: PLC0415
    from asset_dashboard.version_ingestion.routes import router as version_ingestion_router  # noqa: PLC0415
    from asset_dashboard.web.dashboard import pages_router as dashboard_pages_router  # noqa: PLC0415

    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(profiles_router)
    app.include_router(profiles_pages_router)
    app.include_router(discovery_router)
    app.include_router(discovery_pages_router)
    app.include_router(history_router)
    app.include_router(history_pages_router)
    app.include_router(scheduling_router)
    app.include_router(scheduling_pages_router)
    app.include_router(nse_router)
    app.include_router(settings_router)
    app.include_router(settings_pages_router)
    app.include_router(tool_router)
    app.include_router(tool_pages_router)
    app.include_router(dashboard_pages_router)
    app.include_router(reference_versions_router)
    app.include_router(reference_versions_pages_router)
    app.include_router(version_ingestion_router)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "asset_dashboard.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )

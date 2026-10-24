"""Profile routes (FR-001-FR-014, FR-027, FR-042). See contracts/http-api-delta.md."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from asset_dashboard.audit.log import record_event
from asset_dashboard.auth.authz import session_context
from asset_dashboard.db.base import get_session
from asset_dashboard.db.models import AuditEventType, DiscoveryProfile
from asset_dashboard.discovery.nmap_runner import build_nmap_command
from asset_dashboard.nse.allowlist import enabled_script_ids, scope_warnings_for_selection
from asset_dashboard.profiles.service import (
    ProfileInput,
    ProfileNotFoundError,
    StaleVersionError,
    create_profile,
    delete_profile,
    duplicate_profile,
    get_profile,
    list_profiles,
    update_profile,
)
from asset_dashboard.profiles.validation import validate_profile
from asset_dashboard.web.errors import api_error, validation_error
from asset_dashboard.web.templating import templates

router = APIRouter(prefix="/api/profiles")
pages_router = APIRouter()

# Visible stand-in used only for the command preview when a profile has no
# saved target yet (FR-009). Never used for an actual scan.
PREVIEW_PLACEHOLDER_TARGET = "<ціль>"


@pages_router.get("/profiles")
def profiles_list_page(request: Request, session: Session = Depends(get_session)):
    profiles = list_profiles(session)
    return templates.TemplateResponse(
        request,
        "profiles_list.html",
        {
            "profiles": [
                {**_serialize(p), "has_schedule": False} for p in profiles
            ],
            **session_context(request, session),
        },
    )


@pages_router.get("/profiles/new")
def profile_new_page(request: Request, session: Session = Depends(get_session)):
    return templates.TemplateResponse(
        request,
        "profile_editor.html",
        {"profile": None, **session_context(request, session)},
    )


# Blank defaults for an ad-hoc ("custom") scan opened without a profile.
_BLANK_SCAN_CONFIG = {
    "id": None,
    "name": "",
    "target_scope": [],
    "port_spec": "",
    "scan_params": {"timing": "T3"},
    "extracted_fields": ["open_ports", "service_version"],
    "selected_scripts": [],
    "compliance_settings": {},
    "cache_freshness_seconds": 3600,
}


def _parse_targets(targets: str | None) -> list[str] | None:
    if targets is None:
        return None
    return [t.strip() for t in targets.split(",") if t.strip()]


@pages_router.get("/scan")
def custom_scan_page(
    request: Request, targets: str | None = None, session: Session = Depends(get_session)
):
    """Feature 009 (course-corrected): a fully editable one-off ("custom") scan
    with no saved profile. Start Scan runs ad-hoc; Save as Profile persists it."""
    return templates.TemplateResponse(
        request,
        "scan_config.html",
        {
            "profile": dict(_BLANK_SCAN_CONFIG),
            "prefill_targets": _parse_targets(targets),
            **session_context(request, session),
        },
    )


@pages_router.get("/profiles/{profile_id}/scan")
def profile_scan_config_page(
    profile_id: str,
    request: Request,
    targets: str | None = None,
    session: Session = Depends(get_session),
):
    """Feature 009: the Scan Configuration page, reused by Run now and by the
    "Scan selected with profile…" pivot. Pre-filled from the saved profile;
    an optional `?targets=` comma-separated list overrides the displayed
    target field (the scan pivot's selected hosts). 404 when missing."""
    try:
        profile = get_profile(session, profile_id)
    except ProfileNotFoundError:
        return JSONResponse(status_code=404, content=api_error("not_found", "Profile not found."))

    return templates.TemplateResponse(
        request,
        "scan_config.html",
        {
            "profile": _serialize(profile),
            "prefill_targets": _parse_targets(targets),
            **session_context(request, session),
        },
    )


@pages_router.get("/profiles/{profile_id}")
def profile_edit_page(profile_id: str, request: Request, session: Session = Depends(get_session)):
    try:
        profile = get_profile(session, profile_id)
    except ProfileNotFoundError:
        return JSONResponse(status_code=404, content=api_error("not_found", "Profile not found."))
    return templates.TemplateResponse(
        request,
        "profile_editor.html",
        {"profile": profile, **session_context(request, session)},
    )


class ProfileIn(BaseModel):
    name: str
    description: str | None = None
    target_scope: list[str] = Field(default_factory=list)
    port_spec: str = ""
    scan_params: dict = Field(default_factory=dict)
    extracted_fields: list[str] = Field(default_factory=list)
    selected_scripts: list[str] = Field(default_factory=list)
    compliance_settings: dict = Field(default_factory=dict)
    cache_freshness_seconds: int = 3600
    # Accepted-but-ignored for backward compatibility with a legacy client
    # payload (FR-004): the host-management-link capability is removed.
    host_links: list[dict] = Field(default_factory=list)


class ProfileUpdateIn(ProfileIn):
    version_token: int


def _serialize(profile: DiscoveryProfile) -> dict:
    return {
        "id": profile.id,
        "name": profile.name,
        "description": profile.description,
        "target_scope": profile.target_scope,
        "port_spec": profile.port_spec,
        "scan_params": profile.scan_params,
        "extracted_fields": profile.extracted_fields,
        "selected_scripts": profile.selected_scripts,
        "compliance_settings": profile.compliance_settings,
        "cache_freshness_seconds": profile.cache_freshness_seconds,
        "version_token": profile.version_token,
    }


@router.get("")
def api_list_profiles(session: Session = Depends(get_session)):
    return [_serialize(p) for p in list_profiles(session)]


@router.get("/{profile_id}")
def api_get_profile(profile_id: str, session: Session = Depends(get_session)):
    try:
        profile = get_profile(session, profile_id)
    except ProfileNotFoundError:
        return JSONResponse(status_code=404, content=api_error("not_found", "Profile not found."))
    return _serialize(profile)


def _default_scan_params(scan_params: dict) -> dict:
    """New profiles default `timing` to T3 when not specified (FR-001)."""
    merged = dict(scan_params)
    merged.setdefault("timing", "T3")
    return merged


@router.post("", status_code=201)
def api_create_profile(body: ProfileIn, session: Session = Depends(get_session)):
    scan_params = _default_scan_params(body.scan_params)
    payload = body.model_dump() | {"scan_params": scan_params}
    errors = validate_profile(
        payload, allowlisted_script_ids=enabled_script_ids(session), require_target=False
    )
    if errors:
        return validation_error(errors)

    profile = create_profile(
        session,
        ProfileInput(
            name=body.name,
            description=body.description,
            target_scope=body.target_scope,
            port_spec=body.port_spec,
            scan_params=scan_params,
            extracted_fields=body.extracted_fields,
            selected_scripts=body.selected_scripts,
            compliance_settings=body.compliance_settings,
            cache_freshness_seconds=body.cache_freshness_seconds,
        ),
    )
    record_event(
        session,
        AuditEventType.PROFILE_CHANGE,
        detail={"action": "create", "profile_id": profile.id, "name": profile.name},
    )
    session.commit()
    result = _serialize(profile)
    warnings = scope_warnings_for_selection(session, profile.selected_scripts, profile.port_spec)
    if warnings:
        result["warnings"] = warnings
    return result


@router.put("/{profile_id}")
def api_update_profile(
    profile_id: str, body: ProfileUpdateIn, session: Session = Depends(get_session)
):
    payload = body.model_dump()
    errors = validate_profile(
        payload, allowlisted_script_ids=enabled_script_ids(session), require_target=False
    )
    if errors:
        return validation_error(errors)

    try:
        profile = update_profile(
            session,
            profile_id,
            ProfileInput(
                name=body.name,
                description=body.description,
                target_scope=body.target_scope,
                port_spec=body.port_spec,
                scan_params=body.scan_params,
                extracted_fields=body.extracted_fields,
                selected_scripts=body.selected_scripts,
                compliance_settings=body.compliance_settings,
                cache_freshness_seconds=body.cache_freshness_seconds,
            ),
            expected_version_token=body.version_token,
        )
    except ProfileNotFoundError:
        return JSONResponse(status_code=404, content=api_error("not_found", "Profile not found."))
    except StaleVersionError:
        return JSONResponse(
            status_code=409,
            content=api_error(
                "stale_version",
                "This profile was modified by someone else since you loaded it. "
                "Reload and reapply your changes.",
            ),
        )

    record_event(
        session,
        AuditEventType.PROFILE_CHANGE,
        detail={"action": "update", "profile_id": profile.id, "name": profile.name},
    )
    session.commit()
    result = _serialize(profile)
    warnings = scope_warnings_for_selection(session, profile.selected_scripts, profile.port_spec)
    if warnings:
        result["warnings"] = warnings
    return result


@router.post("/preview-command")
def api_preview_command(body: ProfileIn, session: Session = Depends(get_session)):
    """Return the exact nmap argv this (unsaved) payload would execute
    (FR-008) — reuses the same builder the runner uses, so preview and
    execution cannot diverge."""
    scan_params = _default_scan_params(body.scan_params)
    payload = body.model_dump() | {"scan_params": scan_params}
    # FR-008: preview tolerates a missing target so a brand-new profile shows
    # a complete command immediately; other validation (ports, scripts, …)
    # still applies.
    errors = validate_profile(
        payload, allowlisted_script_ids=enabled_script_ids(session), require_target=False
    )
    if errors:
        return validation_error(errors)

    # When no target is set, preview against a single visible placeholder so
    # the command is complete and clearly marked rather than blank (FR-009).
    target_scope = body.target_scope or [PREVIEW_PLACEHOLDER_TARGET]
    command = build_nmap_command(
        target_scope,
        body.port_spec,
        scan_params,
        body.extracted_fields,
        body.selected_scripts,
    )
    return {"command": command, "display": " ".join(command)}


@router.post("/{profile_id}/duplicate", status_code=201)
def api_duplicate_profile(
    profile_id: str, request: Request, session: Session = Depends(get_session)
):
    try:
        source = get_profile(session, profile_id)
        new_name = f"{source.name} (copy)"
        copy = duplicate_profile(session, profile_id, new_name)
    except ProfileNotFoundError:
        return JSONResponse(status_code=404, content=api_error("not_found", "Profile not found."))

    record_event(
        session,
        AuditEventType.PROFILE_CHANGE,
        detail={"action": "duplicate", "source_id": profile_id, "new_id": copy.id},
    )
    session.commit()
    if request.headers.get("HX-Request"):
        row_macro = templates.env.get_template("_macros.html").module.profile_row
        html = row_macro({**_serialize(copy), "has_schedule": False})
        return HTMLResponse(content=str(html), status_code=201)
    return _serialize(copy)


@router.delete("/{profile_id}", status_code=204)
def api_delete_profile(profile_id: str, request: Request, session: Session = Depends(get_session)):
    try:
        delete_profile(session, profile_id)
    except ProfileNotFoundError:
        return JSONResponse(status_code=404, content=api_error("not_found", "Profile not found."))

    record_event(
        session,
        AuditEventType.PROFILE_CHANGE,
        detail={"action": "delete", "profile_id": profile_id},
    )
    session.commit()
    return Response(status_code=204)

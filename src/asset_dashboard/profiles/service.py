"""Profile CRUD + duplicate + optimistic concurrency (FR-007, FR-027, FR-042).

Feature 002: the host-management-link capability is removed (FR-004) —
`HostLinkTemplate` rows are no longer read or written here (the table is
left dormant, per research.md §5). `selected_scripts` (NSE allow-list ids)
is the new per-profile field (FR-010).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from asset_dashboard.db.models import DiscoveryProfile


class StaleVersionError(Exception):
    """Raised when a save targets an outdated version_token (FR-042)."""


class ProfileNotFoundError(Exception):
    pass


@dataclass
class ProfileInput:
    name: str
    description: str | None
    target_scope: list[str]
    port_spec: str
    scan_params: dict
    extracted_fields: list[str]
    compliance_settings: dict
    cache_freshness_seconds: int
    selected_scripts: list[str] = field(default_factory=list)


def list_profiles(session: Session) -> list[DiscoveryProfile]:
    return session.query(DiscoveryProfile).order_by(DiscoveryProfile.name).all()


def get_profile(session: Session, profile_id: str) -> DiscoveryProfile:
    profile = session.get(DiscoveryProfile, profile_id)
    if profile is None:
        raise ProfileNotFoundError(profile_id)
    return profile


def create_profile(session: Session, data: ProfileInput) -> DiscoveryProfile:
    profile = DiscoveryProfile(
        name=data.name,
        description=data.description,
        target_scope=data.target_scope,
        port_spec=data.port_spec,
        scan_params=data.scan_params,
        extracted_fields=data.extracted_fields,
        selected_scripts=data.selected_scripts,
        compliance_settings=data.compliance_settings,
        cache_freshness_seconds=data.cache_freshness_seconds,
        version_token=1,
    )
    session.add(profile)
    session.flush()
    return profile


def update_profile(
    session: Session, profile_id: str, data: ProfileInput, expected_version_token: int
) -> DiscoveryProfile:
    profile = get_profile(session, profile_id)

    if profile.version_token != expected_version_token:
        raise StaleVersionError(
            f"profile {profile_id} is at version {profile.version_token}, "
            f"but update targeted version {expected_version_token}"
        )

    profile.name = data.name
    profile.description = data.description
    profile.target_scope = data.target_scope
    profile.port_spec = data.port_spec
    profile.scan_params = data.scan_params
    profile.extracted_fields = data.extracted_fields
    profile.selected_scripts = data.selected_scripts
    profile.compliance_settings = data.compliance_settings
    profile.cache_freshness_seconds = data.cache_freshness_seconds
    profile.version_token += 1

    session.add(profile)
    session.flush()
    return profile


def duplicate_profile(session: Session, profile_id: str, new_name: str) -> DiscoveryProfile:
    source = get_profile(session, profile_id)
    copy = DiscoveryProfile(
        name=new_name,
        description=source.description,
        target_scope=list(source.target_scope),
        port_spec=source.port_spec,
        scan_params=dict(source.scan_params),
        extracted_fields=list(source.extracted_fields),
        selected_scripts=list(source.selected_scripts),
        compliance_settings=dict(source.compliance_settings),
        cache_freshness_seconds=source.cache_freshness_seconds,
        version_token=1,
    )
    session.add(copy)
    session.flush()
    return copy


def delete_profile(session: Session, profile_id: str) -> None:
    """Remove the profile from active use. Historical DiscoveryRun rows are
    NOT cascaded here — they retain a profile_snapshot and survive deletion
    (FR-027)."""
    profile = get_profile(session, profile_id)
    session.delete(profile)
    session.flush()

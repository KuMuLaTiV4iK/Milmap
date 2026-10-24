"""Freshness-window cache reuse (FR-024, FR-025).

A request to run a profile within its `cache_freshness_seconds` window may
reuse the most recent COMPLETED run instead of re-scanning the network.
The cached response is clearly labelled (`served_from_cache`) and carries
the ORIGINAL run's timestamp, never a new one. `force_fresh` bypasses this
entirely (handled by the caller, which simply skips calling this module).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from asset_dashboard.db.models import (
    ComplianceFinding,
    DiscoveredAsset,
    DiscoveryProfile,
    DiscoveryRun,
    RunStatus,
    RunTrigger,
    utcnow,
)


def find_fresh_run(session: Session, profile: DiscoveryProfile) -> DiscoveryRun | None:
    """Most recent COMPLETED run of this profile, if still within its
    freshness window; otherwise None (a cache miss)."""
    latest = (
        session.query(DiscoveryRun)
        .filter(DiscoveryRun.profile_id == profile.id, DiscoveryRun.status == RunStatus.COMPLETED)
        .order_by(DiscoveryRun.started_at.desc())
        .first()
    )
    if latest is None:
        return None

    age_seconds = (utcnow() - latest.started_at).total_seconds()
    if age_seconds > profile.cache_freshness_seconds:
        return None
    return latest


def serve_from_cache(
    session: Session,
    profile: DiscoveryProfile,
    source_run: DiscoveryRun,
    *,
    trigger: RunTrigger,
    triggered_by_id: str | None,
) -> DiscoveryRun:
    """Create a new DiscoveryRun row that reuses source_run's results,
    clearly labelled as cached and carrying the source's original timestamp."""
    new_run = DiscoveryRun(
        profile_id=profile.id,
        profile_snapshot={
            "name": profile.name,
            "target_scope": profile.target_scope,
            "port_spec": profile.port_spec,
            "scan_params": profile.scan_params,
        },
        trigger=trigger,
        triggered_by_id=triggered_by_id,
        status=RunStatus.COMPLETED,
        served_from_cache=True,
        source_run_id=source_run.id,
        started_at=source_run.started_at,  # label with the ORIGINAL run's time
        finished_at=source_run.finished_at,
        params_used=dict(source_run.params_used),
        summary=dict(source_run.summary),
    )
    session.add(new_run)
    session.flush()

    for asset in source_run.assets:
        asset_copy = DiscoveredAsset(
            run_id=new_run.id,
            address=asset.address,
            state=asset.state,
            open_ports=list(asset.open_ports),
            extracted=dict(asset.extracted),
            management_link=asset.management_link,
        )
        session.add(asset_copy)
        session.flush()

        for finding in asset.findings:
            session.add(
                ComplianceFinding(
                    asset_id=asset_copy.id,
                    control=finding.control,
                    result=finding.result,
                    detail=dict(finding.detail),
                )
            )

    session.flush()
    return new_run

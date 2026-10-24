"""History listing + retention (FR-022, FR-023, FR-026, FR-027)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from asset_dashboard.config import settings
from asset_dashboard.db.models import DiscoveryRun


def list_runs(
    session: Session,
    *,
    profile_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    include_archived: bool = False,
) -> list[DiscoveryRun]:
    """Newest-first listing of runs (FR-023). Archived runs (archival.py —
    a row-count-based "oldest 50 past 100" soft-hide, never a delete) are
    excluded by default; `include_archived=True` surfaces them too."""
    query = session.query(DiscoveryRun).order_by(DiscoveryRun.started_at.desc())
    if profile_id:
        query = query.filter(DiscoveryRun.profile_id == profile_id)
    if status:
        query = query.filter(DiscoveryRun.status == status)
    if not include_archived:
        query = query.filter(DiscoveryRun.archived.is_(False))
    return query.offset(offset).limit(limit).all()


def enforce_retention(session: Session, profile_id: str | None) -> int:
    """Delete the oldest runs for a profile beyond the configured retention
    count (FR-026). A None profile_id (profile already deleted) is skipped —
    those runs are retained indefinitely by design (FR-027). Returns the
    number of runs deleted."""
    limit = settings.history_retention_runs_per_profile
    if limit is None or profile_id is None:
        return 0

    runs = (
        session.query(DiscoveryRun)
        .filter(DiscoveryRun.profile_id == profile_id)
        .order_by(DiscoveryRun.started_at.desc())
        .all()
    )
    to_delete = runs[limit:]
    for run in to_delete:
        session.delete(run)
    if to_delete:
        session.flush()
    return len(to_delete)

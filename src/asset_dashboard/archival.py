"""Row-count-based archival for ever-growing history-style tables
(discovery_runs, schedules, tool_check_runs).

Distinct from history/service.py's `enforce_retention`, which DELETES
runs past a large per-profile cap (500 by default): archiving never
deletes anything. When a table's non-archived row count exceeds
`threshold`, the oldest `batch` of them are flagged `archived=True` so
they drop out of the default listing; `include_archived=true` on a
listing still returns them in full.
"""
from __future__ import annotations

from sqlalchemy import Column
from sqlalchemy.orm import Session

DEFAULT_THRESHOLD = 100
DEFAULT_BATCH = 50


def archive_oldest(
    session: Session,
    model: type,
    order_column: Column,
    *,
    threshold: int = DEFAULT_THRESHOLD,
    batch: int = DEFAULT_BATCH,
) -> int:
    """If `model`'s non-archived row count exceeds `threshold`, mark the
    oldest `batch` rows (by `order_column` ascending) `archived=True`.
    Returns the number of rows archived (0 if under threshold)."""
    count = session.query(model).filter(model.archived.is_(False)).count()
    if count <= threshold:
        return 0

    stale_ids = [
        row[0]
        for row in (
            session.query(model.id)
            .filter(model.archived.is_(False))
            .order_by(order_column.asc())
            .limit(batch)
            .all()
        )
    ]
    if not stale_ids:
        return 0

    session.query(model).filter(model.id.in_(stale_ids)).update(
        {"archived": True}, synchronize_session=False
    )
    return len(stale_ids)

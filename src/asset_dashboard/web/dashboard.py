"""Home ("Головна") page: the 5 most-recently-updated discovery profiles
(each with a Run-now action, usable even without a saved target) and a
recent-scans overview of the 20 most recent runs across ALL profiles
(FR-001-FR-005a).

Feature 002 (FR-020): the default-credential check is a standalone tool,
decoupled from discovery-profile runs, with its own history at
/tools/credential-check — it has no bearing on this page's posture.
"""
from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from asset_dashboard.auth.authz import session_context
from asset_dashboard.db.base import get_session
from asset_dashboard.db.models import (
    ComplianceControl,
    DiscoveryProfile,
    DiscoveryRun,
    Schedule,
)
from asset_dashboard.web.templating import templates

pages_router = APIRouter()

RECENT_PROFILES_LIMIT = 5
RECENT_SCANS_LIMIT = 10
UPCOMING_SCHEDULES_LIMIT = 5


@pages_router.get("/")
def dashboard_page(request: Request, session: Session = Depends(get_session)):
    profiles = (
        session.query(DiscoveryProfile)
        .order_by(DiscoveryProfile.updated_at.desc())
        .limit(RECENT_PROFILES_LIMIT)
        .all()
    )
    recent_profiles = [
        {
            "id": p.id,
            "name": p.name,
            "target_scope": p.target_scope,
            "is_target_less": not p.target_scope,
        }
        for p in profiles
    ]

    runs = (
        session.query(DiscoveryRun)
        .order_by(DiscoveryRun.started_at.desc())
        .limit(RECENT_SCANS_LIMIT)
        .all()
    )
    recent_scans = []
    for run in runs:
        tally: Counter[str] = Counter()
        evaluated = False
        for asset in run.assets:
            for finding in asset.findings:
                if finding.control == ComplianceControl.VERSION_VALIDITY:
                    evaluated = True
                    tally[finding.result.value] += 1
        profile_name = (run.profile_snapshot or {}).get("name", "—")
        recent_scans.append(
            {
                "run": run,
                "profile_name": profile_name,
                "target_scope": (run.params_used or {}).get("target_scope") or [],
                "evaluated": evaluated,
                "posture": dict(tally),
            }
        )

    # Feature 006 (FR-003): the 5 soonest-upcoming *enabled* schedules,
    # each linking to the Schedules page. Disabled schedules are excluded;
    # a missing profile falls back to "(deleted)" like schedules_page.
    upcoming = (
        session.query(Schedule)
        .filter(Schedule.enabled.is_(True))
        .order_by(Schedule.next_run_at.asc())
        .limit(UPCOMING_SCHEDULES_LIMIT)
        .all()
    )
    upcoming_schedules = []
    for schedule in upcoming:
        profile = session.get(DiscoveryProfile, schedule.profile_id)
        upcoming_schedules.append(
            {
                "id": schedule.id,
                "profile_name": profile.name if profile else "(deleted)",
                "label": schedule.label,
                "target_scope": schedule.target_scope,
                "next_run_at": schedule.next_run_at,
            }
        )

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "recent_profiles": recent_profiles,
            "recent_scans": recent_scans,
            "upcoming_schedules": upcoming_schedules,
            **session_context(request, session),
        },
    )

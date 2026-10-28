"""Scheduling engine (FR-028-FR-032).

Schedule state (recurrence, next_run_at, policies) lives in our own
`Schedule` table rather than APScheduler's persistent job store, so the
due-check/overlap/catch-up logic is plain, synchronous, directly
unit-testable code (`tick()`), independent of any live background
scheduler. APScheduler is used only as the periodic heartbeat that calls
`tick()` — see `start_scheduler`/`shutdown_scheduler`, wired into the
app's lifespan.
"""

from __future__ import annotations

import calendar
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from asset_dashboard.db.base import session_scope
from asset_dashboard.db.models import (
    CatchUpPolicy,
    DiscoveryProfile,
    OverlapPolicy,
    RunTrigger,
    Schedule,
    ToolTask,
    utcnow,
)
from asset_dashboard.discovery.runner import AlreadyRunningError, start_run


class UnsupportedRecurrenceError(ValueError):
    pass


class RecurrenceValidationError(ValueError):
    """A recurrence shape is well-typed but its fields are invalid (e.g. a
    past `once` time or `every < 1`). Surfaced to callers as a 422 against
    the `recurrence` field (feature 005 / contracts/http-api-delta.md)."""


# Feature 005 — unit-based interval schedules. Order matters only for the
# human-facing validation message ("one of minute, hour, day, week, month").
_INTERVAL_UNITS: tuple[str, ...] = ("minute", "hour", "day", "week", "month")


def add_months(dt: datetime, n: int) -> datetime:
    """Advance `dt` by `n` calendar months, clamping the day to the target
    month's last valid day (e.g. Jan 31 + 1 month -> Feb 28/29). Stdlib only
    (no `dateutil`), per research D3."""
    month_index = dt.month - 1 + n
    year = dt.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return dt.replace(year=year, month=month, day=min(dt.day, last_day))


def is_one_shot(recurrence: dict) -> bool:
    """True for a one-time ("once") recurrence — the predicate that gates the
    fire-then-disable handling in `tick()` (research D2)."""
    return recurrence.get("type") == "once"


def _parse_run_at(value) -> datetime:
    """Parse a `once` recurrence's `run_at` into a naive-UTC datetime (the
    engine's comparison basis). Accepts the browser's ISO-8601 string, with
    or without a trailing `Z`/offset; any offset is converted to UTC."""
    if not isinstance(value, str) or not value.strip():
        raise RecurrenceValidationError("run_at is required")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise RecurrenceValidationError("run_at must be a valid date/time") from exc
    if parsed.tzinfo is not None:
        parsed = (parsed - parsed.utcoffset()).replace(tzinfo=None)
    return parsed


def compute_next_run_at(recurrence: dict, after: datetime) -> datetime:
    """Compute the next occurrence strictly after `after`.

    For a one-time (`once`) recurrence this returns the fixed `run_at`
    instant regardless of `after` — it is used only to seed `next_run_at`
    at create/update time; `tick()` never reschedules a once schedule.
    """
    kind = recurrence.get("type")

    if kind == "once":
        return _parse_run_at(recurrence.get("run_at"))

    if kind == "interval":
        # Feature 005 unit form: {"every": N, "unit": "minute|hour|day|week|month"}.
        if "unit" in recurrence or "every" in recurrence:
            every = int(recurrence["every"])
            unit = recurrence["unit"]
            if unit == "month":
                return add_months(after, every)
            per_unit = {
                "minute": timedelta(minutes=1),
                "hour": timedelta(hours=1),
                "day": timedelta(days=1),
                "week": timedelta(days=7),
            }[unit]
            return after + every * per_unit
        # Legacy form: {"seconds": N}.
        seconds = int(recurrence["seconds"])
        if seconds <= 0:
            raise UnsupportedRecurrenceError("interval seconds must be positive")
        return after + timedelta(seconds=seconds)

    if kind == "daily":
        hour, minute = int(recurrence["hour"]), int(recurrence["minute"])
        candidate = after.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= after:
            candidate += timedelta(days=1)
        return candidate

    if kind == "weekly":
        hour, minute = int(recurrence["hour"]), int(recurrence["minute"])
        target_dow = int(recurrence["day_of_week"])  # 0=Monday .. 6=Sunday
        candidate = after.replace(hour=hour, minute=minute, second=0, microsecond=0)
        days_ahead = (target_dow - candidate.weekday()) % 7
        candidate += timedelta(days=days_ahead)
        if candidate <= after:
            candidate += timedelta(days=7)
        return candidate

    raise UnsupportedRecurrenceError(f"unsupported recurrence type: {kind!r}")


def validate_recurrence(recurrence: dict, *, now: datetime) -> None:
    """Validate a recurrence shape at create/update time (feature 005).

    Raises `RecurrenceValidationError` (invalid fields) or
    `UnsupportedRecurrenceError` (unknown `type`); both carry a message the
    routes surface as `422 {recurrence: <msg>}`. Legacy shapes
    (`interval{seconds}`, `daily`, `weekly`) remain valid so the shared
    credential-tool scheduler keeps working (FR-014).
    """
    if not isinstance(recurrence, dict):
        raise RecurrenceValidationError("recurrence must be an object")
    kind = recurrence.get("type")

    if kind == "once":
        run_at = _parse_run_at(recurrence.get("run_at"))
        if run_at <= now:
            raise RecurrenceValidationError("run_at must be in the future")
        return

    if kind == "interval":
        if "unit" in recurrence or "every" in recurrence:
            every = recurrence.get("every")
            if not isinstance(every, int) or isinstance(every, bool) or every < 1:
                raise RecurrenceValidationError("every must be a positive whole number")
            if recurrence.get("unit") not in _INTERVAL_UNITS:
                raise RecurrenceValidationError("unit must be one of " + ", ".join(_INTERVAL_UNITS))
            return
        seconds = recurrence.get("seconds")
        if not isinstance(seconds, int) or isinstance(seconds, bool) or seconds < 1:
            raise RecurrenceValidationError("seconds must be a positive whole number")
        return

    if kind in ("daily", "weekly"):
        hour, minute = recurrence.get("hour"), recurrence.get("minute")
        if not (isinstance(hour, int) and 0 <= hour <= 23):
            raise RecurrenceValidationError("hour must be between 0 and 23")
        if not (isinstance(minute, int) and 0 <= minute <= 59):
            raise RecurrenceValidationError("minute must be between 0 and 59")
        if kind == "weekly":
            dow = recurrence.get("day_of_week")
            if not (isinstance(dow, int) and 0 <= dow <= 6):
                raise RecurrenceValidationError("day_of_week must be between 0 and 6")
        return

    raise UnsupportedRecurrenceError(f"unsupported recurrence type: {kind!r}")


def _is_severely_overdue(schedule: Schedule, now: datetime) -> bool:
    """True when the schedule missed more than one full cycle while the
    app was not running — the signal catch_up_policy=skip reacts to."""
    try:
        one_cycle_later = compute_next_run_at(schedule.recurrence, schedule.next_run_at)
    except UnsupportedRecurrenceError:
        return False
    return now > one_cycle_later


def tick(session: Session, *, now: datetime | None = None) -> list[str]:
    """Scan all enabled schedules AND due ToolTasks (FR-021) and trigger them.

    Returns the list of run_ids started (for test observability) — both
    DiscoveryRun ids and ToolCheckRun ids.
    """
    now = now or utcnow()
    started_run_ids: list[str] = []

    due_schedules = (
        session.query(Schedule)
        .filter(Schedule.enabled.is_(True), Schedule.next_run_at <= now)
        .all()
    )

    for schedule in due_schedules:
        profile = session.get(DiscoveryProfile, schedule.profile_id)
        if profile is None:
            continue  # orphaned schedule (profile deleted without cascading in this path)

        one_shot = is_one_shot(schedule.recurrence)  # feature 005: fire once, then disable

        if _is_severely_overdue(schedule, now) and schedule.catch_up_policy == CatchUpPolicy.SKIP:
            if one_shot:
                # Its single moment passed while we were down; disable without
                # firing and never recompute (a once schedule cannot advance).
                schedule.enabled = False
                session.add(schedule)
                continue
            # Skip the missed occurrence(s); jump straight to the next one >= now.
            next_at = schedule.next_run_at
            while next_at <= now:
                next_at = compute_next_run_at(schedule.recurrence, next_at)
            schedule.next_run_at = next_at
            session.add(schedule)
            continue

        try:
            run = start_run(
                session,
                profile,
                trigger=RunTrigger.SCHEDULED,
                triggered_by_id=None,
                target_override=schedule.target_scope,
            )
            started_run_ids.append(run.id)
            schedule.last_triggered_at = now
            if one_shot:
                # One-shot: mark completed (enabled=False + last_triggered_at)
                # and DO NOT recompute next_run_at, so it never re-fires.
                schedule.enabled = False
            else:
                schedule.next_run_at = compute_next_run_at(schedule.recurrence, now)
            session.add(schedule)
        except AlreadyRunningError:
            if one_shot:
                # SKIP: its moment passed while a run was in progress — disable
                # it. QUEUE: leave it enabled/unchanged so the next tick retries
                # the single fire once the in-progress run frees up.
                if schedule.overlap_policy == OverlapPolicy.SKIP:
                    schedule.enabled = False
                    session.add(schedule)
            elif schedule.overlap_policy == OverlapPolicy.SKIP:
                schedule.next_run_at = compute_next_run_at(schedule.recurrence, now)
                session.add(schedule)
            # OverlapPolicy.QUEUE (recurring): leave next_run_at as-is so the next
            # tick retries as soon as the in-progress run finishes — never
            # launches a duplicate concurrent run (FR-031/FR-043).

    started_run_ids.extend(_tick_tool_tasks(session, now))

    if started_run_ids or due_schedules:
        session.commit()

    return started_run_ids


def _tick_tool_tasks(session: Session, now: datetime) -> list[str]:
    """The ToolTask half of tick() (FR-020, FR-021): identical due/overlap/
    catch-up/one-shot handling as Schedule, dispatched through
    tools/credential_tool/tasks.py instead of discovery/runner.py."""
    from asset_dashboard.tools.credential_tool.tasks import dispatch_tool_task, has_running_run

    started_run_ids: list[str] = []
    due_tasks = (
        session.query(ToolTask)
        .filter(ToolTask.enabled.is_(True), ToolTask.next_run_at <= now)
        .all()
    )

    for task in due_tasks:
        one_shot = is_one_shot(task.recurrence)  # a "once" task fires once, then disables

        if _is_severely_overdue(task, now) and task.catch_up_policy == CatchUpPolicy.SKIP:
            if one_shot:
                # Its single moment passed while the app was down; disable it
                # without firing and never recompute (a once task can't advance).
                task.enabled = False
                session.add(task)
                continue
            next_at = task.next_run_at
            while next_at <= now:
                next_at = compute_next_run_at(task.recurrence, next_at)
            task.next_run_at = next_at
            session.add(task)
            continue

        if has_running_run(session, task.id):
            if one_shot:
                # SKIP: its moment passed while a run was in progress — disable.
                # QUEUE: leave it enabled so the next tick retries the single fire.
                if task.overlap_policy == OverlapPolicy.SKIP:
                    task.enabled = False
                    session.add(task)
            elif task.overlap_policy == OverlapPolicy.SKIP:
                task.next_run_at = compute_next_run_at(task.recurrence, now)
                session.add(task)
            # OverlapPolicy.QUEUE (recurring): leave next_run_at as-is, same as Schedule.
            continue

        run = dispatch_tool_task(session, task)
        started_run_ids.append(run.id)
        task.last_triggered_at = now
        if one_shot:
            # One-shot: mark completed (enabled=False + last_triggered_at) and
            # DO NOT recompute next_run_at, so it never re-fires (mirrors Schedule).
            task.enabled = False
        else:
            task.next_run_at = compute_next_run_at(task.recurrence, now)
        session.add(task)

    return started_run_ids


_scheduler = None


def start_scheduler(tick_seconds: int | None = None) -> None:
    """Start the APScheduler heartbeat that calls tick() periodically."""
    global _scheduler
    if _scheduler is not None:
        return

    from apscheduler.schedulers.background import BackgroundScheduler

    from asset_dashboard.config import settings

    def _run_tick() -> None:
        with session_scope() as session:
            tick(session)

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        _run_tick, "interval", seconds=tick_seconds or settings.scheduler_tick_seconds
    )
    _scheduler.start()


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None

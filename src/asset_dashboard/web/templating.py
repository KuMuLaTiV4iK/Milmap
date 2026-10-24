"""Shared Jinja2 environment for server-rendered pages."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi.templating import Jinja2Templates

from asset_dashboard.discovery.results_view import port_row_view
from asset_dashboard.web.i18n import help_for, t

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# All UI timestamps use this format, in the host's local time zone.
TIMESTAMP_FORMAT = "%d.%m.%y %H:%M:%S"


def local_ts(value) -> str:
    """Render a timestamp (a `datetime`, or a naive-/aware ISO string) in the
    HOST's local time zone as `DD.MM.YY HH:MM:SS`. Naive values are treated as
    UTC (that is how the app stores them), then converted to host-local time so
    a schedule created in local time reads back in local time. Returns the
    original value when it cannot be parsed, and "" for None."""
    if value is None:
        return ""
    parsed = value
    if isinstance(value, str):
        text = value.strip()
        if not text or text == "—":
            return value
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return value
    if not isinstance(parsed, datetime):
        return str(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    # astimezone() with no argument converts to the host's local time zone.
    return parsed.astimezone().strftime(TIMESTAMP_FORMAT)


def humanize_recurrence(recurrence: dict) -> str:
    """Ukrainian, human-readable rendering of a recurrence object for the
    schedules list (feature 005, research D7). Covers the two discovery-UI
    shapes (once / unit-interval) and keeps a readable fallback for the
    legacy shapes the engine still understands (interval{seconds}, daily,
    weekly)."""
    if not isinstance(recurrence, dict):
        return str(recurrence)
    kind = recurrence.get("type")

    if kind == "once":
        # The exact instant lives in the dedicated "Next run" column, so the
        # recurrence label stays just the kind (no duplicated timestamp).
        return t("schedules.kind_once")

    if kind == "interval":
        if "unit" in recurrence or "every" in recurrence:
            unit_name = t(f"schedules.unit_{recurrence.get('unit')}")
            return f"{t('schedules.interval_every')} {recurrence.get('every')} {unit_name}"
        return f"{t('schedules.kind_interval')}: {recurrence.get('seconds')} с"

    if kind == "daily":
        hour, minute = int(recurrence.get("hour", 0)), int(recurrence.get("minute", 0))
        return f"Щодня о {hour:02d}:{minute:02d}"

    if kind == "weekly":
        return (
            f"Щотижня о {int(recurrence.get('hour', 0)):02d}:"
            f"{int(recurrence.get('minute', 0)):02d}"
        )

    return str(recurrence)


def is_completed_once(schedule: dict) -> bool:
    """True when a schedule row is a fired, one-time schedule: a `once`
    recurrence that is no longer enabled and has a recorded fire time
    (feature 005 completion marker)."""
    recurrence = schedule.get("recurrence") or {}
    return (
        isinstance(recurrence, dict)
        and recurrence.get("type") == "once"
        and not schedule.get("enabled")
        and bool(schedule.get("last_triggered_at"))
    )


templates.env.globals["t"] = t
templates.env.globals["help_for"] = help_for
templates.env.globals["port_row_view"] = port_row_view
templates.env.globals["humanize_recurrence"] = humanize_recurrence
templates.env.globals["is_completed_once"] = is_completed_once
templates.env.filters["localts"] = local_ts

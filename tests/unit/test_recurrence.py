"""Unit tests for feature-005 recurrence computation + validation.

Covers the two new discovery-UI recurrence shapes — one-time (`once`) and
unit-based interval (`every` × `unit`) — plus the month end-of-month clamp
and `is_one_shot`. Legacy shapes are exercised in the contract regression
test (tests/contract/test_schedule.py)."""
from datetime import datetime

import pytest

from asset_dashboard.scheduling.engine import (
    RecurrenceValidationError,
    UnsupportedRecurrenceError,
    add_months,
    compute_next_run_at,
    is_one_shot,
    validate_recurrence,
)

NOW = datetime(2026, 10, 22, 12, 0, 0)


# --------------------------------------------------------------------------- once (US1)
def test_once_compute_returns_parsed_run_at():
    rec = {"type": "once", "run_at": "2026-10-25T23:00:00"}
    assert compute_next_run_at(rec, NOW) == datetime(2026, 10, 25, 23, 0, 0)


def test_once_compute_parses_utc_z_suffix_to_naive():
    rec = {"type": "once", "run_at": "2026-10-25T23:00:00Z"}
    assert compute_next_run_at(rec, NOW) == datetime(2026, 10, 25, 23, 0, 0)


def test_once_compute_converts_offset_to_utc():
    rec = {"type": "once", "run_at": "2026-10-25T23:00:00+02:00"}
    assert compute_next_run_at(rec, NOW) == datetime(2026, 10, 25, 21, 0, 0)


def test_is_one_shot_true_for_once_only():
    assert is_one_shot({"type": "once", "run_at": "2026-10-25T23:00:00"}) is True
    assert is_one_shot({"type": "interval", "every": 2, "unit": "hour"}) is False
    assert is_one_shot({"type": "interval", "seconds": 60}) is False


def test_validate_once_accepts_future():
    validate_recurrence({"type": "once", "run_at": "2026-10-25T23:00:00"}, now=NOW)


def test_validate_once_rejects_past():
    with pytest.raises(RecurrenceValidationError):
        validate_recurrence({"type": "once", "run_at": "2026-10-20T10:00:00"}, now=NOW)


def test_validate_once_rejects_equal_to_now():
    with pytest.raises(RecurrenceValidationError):
        validate_recurrence({"type": "once", "run_at": NOW.isoformat()}, now=NOW)


def test_validate_once_rejects_missing_run_at():
    with pytest.raises(RecurrenceValidationError):
        validate_recurrence({"type": "once"}, now=NOW)


def test_validate_once_rejects_unparseable_run_at():
    with pytest.raises(RecurrenceValidationError):
        validate_recurrence({"type": "once", "run_at": "not-a-date"}, now=NOW)


# ---------------------------------------------------------------- interval units (US2)
@pytest.mark.parametrize(
    "unit,expected",
    [
        ("minute", datetime(2026, 10, 22, 12, 2, 0)),
        ("hour", datetime(2026, 10, 22, 14, 0, 0)),
        ("day", datetime(2026, 10, 24, 12, 0, 0)),
        ("week", datetime(2026, 11, 5, 12, 0, 0)),
    ],
)
def test_interval_unit_compute(unit, expected):
    rec = {"type": "interval", "every": 2, "unit": unit}
    assert compute_next_run_at(rec, NOW) == expected


def test_interval_month_compute():
    rec = {"type": "interval", "every": 1, "unit": "month"}
    assert compute_next_run_at(rec, datetime(2026, 3, 15, 8, 0)) == datetime(2026, 4, 15, 8, 0)


def test_add_months_clamps_end_of_month():
    # Jan 31 + 1 month -> Feb 28 (2026 is not a leap year).
    assert add_months(datetime(2026, 1, 31, 9, 30), 1) == datetime(2026, 2, 28, 9, 30)


def test_add_months_leap_year():
    assert add_months(datetime(2028, 1, 31), 1) == datetime(2028, 2, 29)


def test_add_months_wraps_year():
    assert add_months(datetime(2026, 11, 15), 3) == datetime(2027, 2, 15)


def test_interval_month_via_compute_clamps():
    rec = {"type": "interval", "every": 1, "unit": "month"}
    assert compute_next_run_at(rec, datetime(2026, 1, 31, 0, 0)) == datetime(2026, 2, 28, 0, 0)


@pytest.mark.parametrize("unit", ["minute", "hour", "day", "week", "month"])
def test_validate_interval_accepts_all_units(unit):
    validate_recurrence({"type": "interval", "every": 1, "unit": unit}, now=NOW)


def test_validate_interval_rejects_zero_every():
    with pytest.raises(RecurrenceValidationError):
        validate_recurrence({"type": "interval", "every": 0, "unit": "hour"}, now=NOW)


def test_validate_interval_rejects_non_integer_every():
    with pytest.raises(RecurrenceValidationError):
        validate_recurrence({"type": "interval", "every": 2.5, "unit": "hour"}, now=NOW)


def test_validate_interval_rejects_bad_unit():
    with pytest.raises(RecurrenceValidationError):
        validate_recurrence({"type": "interval", "every": 2, "unit": "fortnight"}, now=NOW)


def test_validate_rejects_unknown_type():
    with pytest.raises(UnsupportedRecurrenceError):
        validate_recurrence({"type": "bogus"}, now=NOW)

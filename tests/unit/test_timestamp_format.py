"""All UI timestamps render as DD.MM.YY HH:MM:SS in the host's local zone."""
from __future__ import annotations

import re
from datetime import datetime, timezone

from asset_dashboard.web.templating import local_ts

_FMT = re.compile(r"^\d{2}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}$")


def test_local_ts_shape_for_datetime():
    assert _FMT.match(local_ts(datetime(2026, 10, 22, 17, 9, 53)))


def test_local_ts_shape_for_iso_string():
    assert _FMT.match(local_ts("2026-10-22T20:09:53.427982"))


def test_local_ts_matches_manual_local_conversion():
    naive_utc = datetime(2026, 10, 22, 17, 9, 53)
    expected = naive_utc.replace(tzinfo=timezone.utc).astimezone().strftime("%d.%m.%y %H:%M:%S")
    assert local_ts(naive_utc) == expected


def test_local_ts_passthrough_and_empty():
    assert local_ts("—") == "—"
    assert local_ts(None) == ""
    assert local_ts("not-a-timestamp") == "not-a-timestamp"

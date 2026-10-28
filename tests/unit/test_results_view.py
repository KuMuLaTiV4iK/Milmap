"""FR-009/FR-009a/FR-010: the ports-column rendering model — small
(<=10 distinct ports in the run) lists every port with its state, large
(>10) shows open-only, large-with-no-open-port signals `all_closed`, and
a missing `state` (historical rows) is treated as `open`."""

from asset_dashboard.discovery.results_view import port_row_view

OPEN_AND_FILTERED = [
    {"port": 22, "protocol": "tcp", "state": "open", "service": "ssh"},
    {"port": 8291, "protocol": "tcp", "state": "filtered", "service": "winbox"},
]

ALL_CLOSED = [
    {"port": 22, "protocol": "tcp", "state": "closed", "service": "ssh"},
    {"port": 8291, "protocol": "tcp", "state": "closed", "service": "winbox"},
]

NO_STATE = [
    {"port": 22, "protocol": "tcp", "service": "ssh"},
]


def test_small_scan_lists_every_port_with_state():
    result = port_row_view(2, OPEN_AND_FILTERED)
    assert result["mode"] == "small"
    assert result["ports"] == OPEN_AND_FILTERED
    assert result["all_closed"] is False


def test_large_scan_shows_open_only():
    result = port_row_view(11, OPEN_AND_FILTERED)
    assert result["mode"] == "large"
    assert result["ports"] == [OPEN_AND_FILTERED[0]]
    assert result["all_closed"] is False


def test_large_scan_with_no_open_ports_flags_all_closed():
    result = port_row_view(11, ALL_CLOSED)
    assert result["mode"] == "large"
    assert result["ports"] == []
    assert result["all_closed"] is True


def test_exactly_10_ports_is_small():
    assert port_row_view(10, OPEN_AND_FILTERED)["mode"] == "small"


def test_exactly_11_ports_is_large():
    assert port_row_view(11, OPEN_AND_FILTERED)["mode"] == "large"


def test_missing_state_treated_as_open_in_large_mode():
    result = port_row_view(11, NO_STATE)
    assert result["ports"] == NO_STATE
    assert result["all_closed"] is False

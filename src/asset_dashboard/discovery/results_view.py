"""Ports-column rendering model (FR-009-FR-011).

Fixes the defect where filtered/closed ports render as if open: a scan
whose results contain `ports_in_results` <= 10 distinct `(port, protocol)`
pairs is "small" and shows every port with its actual state; a "large"
scan (>10) shows open-only, since listing every port there would flood
the view with noise. A large-mode host with no open port renders the
"all ports closed/filtered" placeholder rather than an empty cell.

Historical rows persisted before this feature carry no `state` per port
— those are treated as `open` (backward compatible, no backfill).
"""

from __future__ import annotations

SMALL_SCAN_PORT_THRESHOLD = 10


def port_row_view(ports_in_results: int, ports: list[dict]) -> dict:
    """Return `{mode, ports, all_closed}` for one host's ports cell.

    `mode` is "small" or "large", driven by the run-wide
    `ports_in_results` count (not this host's own port count), so every
    row in a run renders consistently.
    """
    mode = "small" if ports_in_results <= SMALL_SCAN_PORT_THRESHOLD else "large"

    if mode == "small":
        return {"mode": mode, "ports": list(ports), "all_closed": False}

    open_ports = [p for p in ports if p.get("state", "open") == "open"]
    return {"mode": mode, "ports": open_ports, "all_closed": len(open_ports) == 0}

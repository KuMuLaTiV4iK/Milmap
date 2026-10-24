"""FR-009b/FR-011: `_persist_assets` stores each port's `state`, computes
`run.summary["ports_in_results"]` as the distinct `(port, protocol)`
count, and selects `service_version` from an OPEN port only."""
from asset_dashboard.db.base import session_scope
from asset_dashboard.db.models import DiscoveryRun
from asset_dashboard.discovery.parser import ParsedHost, ParsedPort
from asset_dashboard.discovery.runner import _persist_assets


def _make_run(session) -> DiscoveryRun:
    run = DiscoveryRun(profile_id=None, params_used={}, summary={})
    session.add(run)
    session.flush()
    return run


def test_persist_assets_stores_state_per_port(client):
    with session_scope() as session:
        run = _make_run(session)
        hosts = [
            ParsedHost(
                address="192.168.1.1",
                up=True,
                ports=[
                    ParsedPort(
                        port=22, protocol="tcp", state="open", service="ssh", version="OpenSSH 7.4"
                    ),
                    ParsedPort(port=8291, protocol="tcp", state="filtered", service="winbox"),
                ],
            )
        ]
        _persist_assets(session, run, hosts, {})
        session.flush()
        asset = run.assets[0]
        states = {p["port"]: p["state"] for p in asset.open_ports}
        assert states == {22: "open", 8291: "filtered"}


def test_persist_assets_sets_ports_in_results_as_distinct_count(client):
    with session_scope() as session:
        run = _make_run(session)
        hosts = [
            ParsedHost(
                address="192.168.1.1",
                up=True,
                ports=[
                    ParsedPort(port=22, protocol="tcp", state="open"),
                    ParsedPort(port=8291, protocol="tcp", state="filtered"),
                ],
            ),
            ParsedHost(
                address="192.168.1.3",
                up=True,
                ports=[
                    ParsedPort(port=22, protocol="tcp", state="open"),
                    ParsedPort(port=8291, protocol="tcp", state="open"),
                ],
            ),
        ]
        _persist_assets(session, run, hosts, {})
        # (22,tcp) and (8291,tcp) — distinct across both hosts, not summed.
        assert run.summary["ports_in_results"] == 2


def test_service_version_selected_from_open_port_only(client):
    with session_scope() as session:
        run = _make_run(session)
        hosts = [
            ParsedHost(
                address="192.168.1.3",
                up=True,
                ports=[
                    ParsedPort(
                        port=22, protocol="tcp", state="filtered", version="should not be picked"
                    ),
                    ParsedPort(
                        port=8291, protocol="tcp", state="open", version="MikroTik WinBox 6.49.19"
                    ),
                ],
            )
        ]
        _persist_assets(session, run, hosts, {})
        asset = run.assets[0]
        assert asset.extracted["service_version"] == "MikroTik WinBox 6.49.19"


def test_service_version_none_when_no_open_port_has_a_version(client):
    with session_scope() as session:
        run = _make_run(session)
        hosts = [
            ParsedHost(
                address="192.168.1.92",
                up=True,
                ports=[
                    ParsedPort(port=22, protocol="tcp", state="closed", version="irrelevant"),
                    ParsedPort(port=8291, protocol="tcp", state="closed", version="irrelevant"),
                ],
            )
        ]
        _persist_assets(session, run, hosts, {})
        asset = run.assets[0]
        assert asset.extracted["service_version"] is None

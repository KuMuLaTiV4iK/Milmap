"""Performance validation at the spec's target scale (SC-012): an
inventory of ~5,000 hosts and a single run covering a /22 (~1,024
addresses), with the history list loading in under 3 seconds.

This seeds data directly via the DB session (bypassing nmap entirely —
scale of the DATA, not of a live scan, is what SC-012 is about) and
measures the actual history-listing query path.
"""

import time

from asset_dashboard.db.base import session_scope
from asset_dashboard.db.models import (
    AssetState,
    DiscoveredAsset,
    DiscoveryProfile,
    DiscoveryRun,
    RunStatus,
    RunTrigger,
)
from asset_dashboard.history.service import list_runs

TARGET_TOTAL_HOSTS = 5_000
HOSTS_PER_RUN = 1_024  # a /22


def test_history_listing_loads_under_3s_at_target_scale(authed_client):
    with session_scope() as session:
        profile = DiscoveryProfile(
            name="Scale Test Profile",
            target_scope=["10.0.0.0/22"],
            port_spec="22",
            scan_params={},
            extracted_fields=["open_ports", "service_version"],
        )
        session.add(profile)
        session.flush()
        profile_id = profile.id

        # Enough runs, each with enough assets, to reach ~5,000 total
        # discovered hosts across history (SC-012's inventory target).
        runs_needed = TARGET_TOTAL_HOSTS // HOSTS_PER_RUN + 1
        for run_index in range(runs_needed):
            run = DiscoveryRun(
                profile_id=profile_id,
                profile_snapshot={"name": profile.name},
                trigger=RunTrigger.MANUAL,
                status=RunStatus.COMPLETED,
                params_used={},
                summary={"hosts": HOSTS_PER_RUN},
            )
            session.add(run)
            session.flush()

            open_ports = [{"port": 22, "protocol": "tcp", "service": "ssh", "version": None}]
            for host_index in range(HOSTS_PER_RUN):
                session.add(
                    DiscoveredAsset(
                        run_id=run.id,
                        address=f"10.{run_index}.{host_index // 256}.{host_index % 256}",
                        state=AssetState.UP,
                        open_ports=open_ports,
                        extracted={"open_ports": [], "service_version": None},
                    )
                )

    # Measure the actual history-listing path used by GET /api/history
    # and the HTML history panel (history/routes.py).
    with session_scope() as session:
        start = time.perf_counter()
        runs = list_runs(session, limit=100)
        elapsed = time.perf_counter() - start

    assert len(runs) >= runs_needed
    assert elapsed < 3.0, f"history listing took {elapsed:.3f}s at scale (SC-012 requires < 3s)"

    # Also measure the actual HTTP endpoint end-to-end (serialization included).
    start = time.perf_counter()
    resp = authed_client.get("/api/history?limit=100")
    elapsed_http = time.perf_counter() - start

    assert resp.status_code == 200
    assert elapsed_http < 3.0, f"GET /api/history took {elapsed_http:.3f}s (SC-012 requires < 3s)"

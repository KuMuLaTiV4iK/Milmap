"""FR-021a/FR-021b: `tick()` passes a schedule's own `target_scope` as the
run's target override, and a schedule's target is validated the same way
a profile's is."""
from datetime import timedelta

from asset_dashboard.db.base import session_scope
from asset_dashboard.db.models import DiscoveryProfile, DiscoveryRun, RunStatus, Schedule, utcnow
from asset_dashboard.discovery import nmap_runner
from asset_dashboard.profiles.validation import validate_target_scope
from asset_dashboard.scheduling.engine import tick

SAMPLE_XML = (
    "<?xml version='1.0'?><nmaprun><host><status state='up'/>"
    "<address addr='10.0.0.9' addrtype='ipv4'/><ports/></host></nmaprun>"
)


class _FakeProcess:
    def __init__(self):
        self.returncode = 0

    def communicate(self):
        return SAMPLE_XML, ""

    def poll(self):
        return self.returncode

    def terminate(self):
        pass


def test_tick_passes_schedule_target_scope_as_override(client, monkeypatch):
    captured: dict = {}

    def fake_start_nmap(
        target_scope, port_spec, scan_params, extracted_fields=None, selected_scripts=None
    ):
        captured["target_scope"] = target_scope
        return nmap_runner.NmapRunHandle(process=_FakeProcess(), command=["nmap"])

    monkeypatch.setattr(nmap_runner, "start_nmap", fake_start_nmap)

    with session_scope() as session:
        profile = DiscoveryProfile(
            name="Target-less schedule test",
            target_scope=[],
            port_spec="22",
            scan_params={"timing": "T3"},
            extracted_fields=[],
        )
        session.add(profile)
        session.flush()
        schedule = Schedule(
            profile_id=profile.id,
            recurrence={"type": "interval", "seconds": 3600},
            target_scope=["10.0.0.9"],
            next_run_at=utcnow() - timedelta(seconds=1),
        )
        session.add(schedule)

    import time

    with session_scope() as session:
        started = tick(session)
    assert len(started) == 1
    run_id = started[0]

    deadline = time.time() + 3.0
    while time.time() < deadline:
        with session_scope() as session:
            run = session.get(DiscoveryRun, run_id)
            if run.status != RunStatus.RUNNING:
                break
        time.sleep(0.02)
    else:
        raise TimeoutError("run did not finish")

    assert captured["target_scope"] == ["10.0.0.9"]


def test_schedule_target_scope_validated_like_profile_target():
    assert validate_target_scope(["10.0.0.0/24"]) is None
    assert validate_target_scope([]) is not None
    assert validate_target_scope(["not-a-target!!"]) is not None

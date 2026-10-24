"""Run lifecycle orchestrator (FR-016-FR-021, FR-043).

Each run executes in a background thread so the triggering HTTP request
returns immediately (202 running) and progress can be polled. A module-
level registry tracks which profiles are currently running (FR-043: no
duplicate concurrent run of the same profile) and the global concurrent-
run count (FR-021).
"""
from __future__ import annotations

import threading
import xml.etree.ElementTree as ET
from uuid import uuid4

from sqlalchemy.orm import Session

from asset_dashboard.archival import archive_oldest
from asset_dashboard.audit.log import record_event
from asset_dashboard.compliance.evaluate import evaluate_asset_compliance
from asset_dashboard.config import settings
from asset_dashboard.db.base import session_scope
from asset_dashboard.db.models import (
    AssetState,
    AuditEventType,
    DiscoveredAsset,
    DiscoveryProfile,
    DiscoveryRun,
    RunStatus,
    RunTrigger,
    utcnow,
)
from asset_dashboard.discovery import nmap_runner
from asset_dashboard.discovery.parser import ParsedHost, parse_nmap_xml
from asset_dashboard.history.service import enforce_retention


class AlreadyRunningError(Exception):
    """A run of this profile is already in progress (FR-043)."""


class ConcurrencyLimitError(Exception):
    """The global concurrent-run limit has been reached (FR-021)."""


_lock = threading.Lock()
_running_profile_ids: set[str] = set()
_cancelled_run_ids: set[str] = set()
_active_handles: dict[str, nmap_runner.NmapRunHandle] = {}


def is_profile_running(profile_id: str) -> bool:
    with _lock:
        return profile_id in _running_profile_ids


def start_run(
    session: Session,
    profile: DiscoveryProfile,
    *,
    trigger: RunTrigger = RunTrigger.MANUAL,
    triggered_by_id: str | None = None,
    target_override: list[str] | None = None,
    port_spec_override: str | None = None,
    scan_params_override: dict | None = None,
    extracted_fields_override: list[str] | None = None,
    selected_scripts_override: list[str] | None = None,
    compliance_settings_override: dict | None = None,
) -> DiscoveryRun:
    # Feature 009: one-off per-run overrides are applied into the run's
    # snapshot only when provided; the DiscoveryProfile row is never written
    # (one-off semantics, FR-017). The fully-editable Scan window sends every
    # changed field as an override, so a profile-linked scan stays in history
    # and cache while reflecting the operator's one-off edits.
    effective_target = (
        list(target_override) if target_override is not None else list(profile.target_scope)
    )
    effective_port_spec = (
        port_spec_override if port_spec_override is not None else profile.port_spec
    )
    effective_scan_params = (
        dict(scan_params_override)
        if scan_params_override is not None
        else dict(profile.scan_params)
    )
    effective_extracted_fields = (
        list(extracted_fields_override)
        if extracted_fields_override is not None
        else list(profile.extracted_fields)
    )
    effective_scripts = (
        list(selected_scripts_override)
        if selected_scripts_override is not None
        else list(profile.selected_scripts)
    )
    effective_compliance = (
        dict(compliance_settings_override)
        if compliance_settings_override is not None
        else dict(profile.compliance_settings)
    )
    params_used = {
        "target_scope": effective_target,
        "port_spec": effective_port_spec,
        "scan_params": effective_scan_params,
        "extracted_fields": effective_extracted_fields,
        "selected_scripts": effective_scripts,
    }
    return _launch(
        session,
        lock_key=profile.id,
        profile_id=profile.id,
        profile_name=profile.name,
        params_used=params_used,
        compliance_settings=effective_compliance,
        trigger=trigger,
        triggered_by_id=triggered_by_id,
        enforce_unique=True,
    )


def start_adhoc_run(
    session: Session,
    *,
    name: str,
    target_scope: list[str],
    port_spec: str,
    scan_params: dict,
    extracted_fields: list[str],
    selected_scripts: list[str],
    compliance_settings: dict,
    trigger: RunTrigger = RunTrigger.MANUAL,
    triggered_by_id: str | None = None,
) -> DiscoveryRun:
    """Feature 009 (course-corrected): launch a one-off scan from a fully
    editable configuration WITHOUT persisting a DiscoveryProfile. The run is
    recorded with no linked profile (``profile_id`` is None) but its complete
    config is snapshotted and audited. The global concurrency limit still
    applies; there is no per-profile "already running" check (there is no
    profile)."""
    params_used = {
        "target_scope": list(target_scope),
        "port_spec": port_spec,
        "scan_params": dict(scan_params),
        "extracted_fields": list(extracted_fields),
        "selected_scripts": list(selected_scripts),
    }
    return _launch(
        session,
        lock_key=f"adhoc:{uuid4().hex}",
        profile_id=None,
        profile_name=name,
        params_used=params_used,
        compliance_settings=dict(compliance_settings),
        trigger=trigger,
        triggered_by_id=triggered_by_id,
        enforce_unique=False,
    )


def _launch(
    session: Session,
    *,
    lock_key: str,
    profile_id: str | None,
    profile_name: str,
    params_used: dict,
    compliance_settings: dict,
    trigger: RunTrigger,
    triggered_by_id: str | None,
    enforce_unique: bool,
) -> DiscoveryRun:
    """Shared launch core for both profile-backed and ad-hoc runs: reserve a
    concurrency slot, persist the RUNNING row + RUN_STARTED audit event, and
    start the background scan thread."""
    with _lock:
        if enforce_unique and lock_key in _running_profile_ids:
            raise AlreadyRunningError(lock_key)
        if len(_running_profile_ids) >= settings.max_concurrent_runs:
            raise ConcurrencyLimitError()
        _running_profile_ids.add(lock_key)

    run = DiscoveryRun(
        profile_id=profile_id,
        profile_snapshot={"name": profile_name, **params_used},
        trigger=trigger,
        triggered_by_id=triggered_by_id,
        status=RunStatus.RUNNING,
        params_used=params_used,
    )
    session.add(run)
    record_event(
        session,
        AuditEventType.RUN_STARTED,
        actor_id=triggered_by_id,
        detail={"run_id_pending": True, "profile_id": profile_id, "trigger": trigger.value},
    )
    session.flush()
    run_id = run.id
    session.commit()

    thread = threading.Thread(
        target=_execute_run,
        args=(run_id, lock_key, params_used, compliance_settings),
        daemon=True,
    )
    thread.start()

    return run


def cancel_run(run_id: str) -> bool:
    with _lock:
        _cancelled_run_ids.add(run_id)
        handle = _active_handles.get(run_id)
    if handle is None:
        return False
    handle.cancel()
    return True


def _execute_run(
    run_id: str,
    lock_key: str,
    params_used: dict,
    compliance_settings: dict,
) -> None:
    try:
        handle = nmap_runner.start_nmap(
            params_used["target_scope"],
            params_used["port_spec"],
            params_used["scan_params"],
            params_used.get("extracted_fields"),
            params_used.get("selected_scripts"),
        )
    except nmap_runner.NmapNotAvailableError as exc:
        _finish_failed(run_id, lock_key, str(exc))
        return

    with _lock:
        _active_handles[run_id] = handle

    stdout, stderr, returncode = nmap_runner.wait_for_result(handle)

    with _lock:
        was_cancelled = run_id in _cancelled_run_ids
        _cancelled_run_ids.discard(run_id)
        _active_handles.pop(run_id, None)
        _running_profile_ids.discard(lock_key)

    if was_cancelled:
        _finish_cancelled(run_id, stdout, compliance_settings)
    elif returncode != 0:
        _finish_failed(run_id, lock_key, stderr or f"nmap exited with code {returncode}")
    else:
        _finish_completed(run_id, stdout, compliance_settings)


def _hosts_from_stdout(stdout: str) -> list[ParsedHost]:
    try:
        return parse_nmap_xml(stdout)
    except ET.ParseError:
        # Incomplete XML (e.g. process cancelled mid-scan) — best-effort: no
        # parseable hosts rather than crashing the run-finishing path.
        return []


def _persist_assets(
    session: Session,
    run: DiscoveryRun,
    hosts: list[ParsedHost],
    compliance_settings: dict,
) -> None:
    responding = [h for h in hosts if h.up]
    distinct_ports: set[tuple[int, str]] = set()

    for host in responding:
        open_ports = [
            {
                "port": p.port,
                "protocol": p.protocol,
                "state": p.state,
                "service": p.service,
                "version": p.version,
            }
            for p in host.ports
        ]
        for p in host.ports:
            distinct_ports.add((p.port, p.protocol))
        service_version = next(
            (p.version for p in host.ports if p.state == "open" and p.version), None
        )
        extracted: dict = {"open_ports": open_ports, "service_version": service_version}
        if host.script_output:
            extracted["nse"] = dict(host.script_output)

        asset = DiscoveredAsset(
            run_id=run.id,
            address=host.address,
            state=AssetState.UP,
            open_ports=open_ports,
            extracted=extracted,
        )
        session.add(asset)
        session.flush()  # need asset.id before attaching compliance findings

        if compliance_settings:
            evaluate_asset_compliance(session, asset, open_ports, compliance_settings)

    run.summary = {"hosts": len(responding), "ports_in_results": len(distinct_ports)}


def _finish_completed(run_id: str, stdout: str, compliance_settings: dict) -> None:
    hosts = _hosts_from_stdout(stdout)
    with session_scope() as session:
        run = session.get(DiscoveryRun, run_id)
        _persist_assets(session, run, hosts, compliance_settings)
        run.status = RunStatus.COMPLETED
        run.finished_at = utcnow()
        record_event(
            session,
            AuditEventType.RUN_FINISHED,
            detail={
                "run_id": run_id,
                "status": "completed",
                "hosts": run.summary.get("hosts", 0),
            },
        )
        enforce_retention(session, run.profile_id)
        archive_oldest(session, DiscoveryRun, DiscoveryRun.started_at)


def _finish_cancelled(run_id: str, stdout: str, compliance_settings: dict) -> None:
    hosts = _hosts_from_stdout(stdout)
    with session_scope() as session:
        run = session.get(DiscoveryRun, run_id)
        # Retain partial results (FR-017).
        _persist_assets(session, run, hosts, compliance_settings)
        run.status = RunStatus.CANCELLED

        run.finished_at = utcnow()
        record_event(
            session,
            AuditEventType.RUN_FINISHED,
            detail={"run_id": run_id, "status": "cancelled"},
        )
        enforce_retention(session, run.profile_id)
        archive_oldest(session, DiscoveryRun, DiscoveryRun.started_at)


def _finish_failed(run_id: str, lock_key: str, error_detail: str) -> None:
    with _lock:
        _running_profile_ids.discard(lock_key)
    with session_scope() as session:
        run = session.get(DiscoveryRun, run_id)
        run.status = RunStatus.FAILED
        run.error_detail = error_detail
        run.finished_at = utcnow()
        record_event(
            session,
            AuditEventType.RUN_FINISHED,
            detail={"run_id": run_id, "status": "failed", "error": error_detail},
        )
        enforce_retention(session, run.profile_id)
        archive_oldest(session, DiscoveryRun, DiscoveryRun.started_at)

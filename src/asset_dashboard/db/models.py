"""ORM models.

This module accumulates entities across user stories (see data-model.md for
the full schema). Each user story's tasks add its own model classes here.
"""
from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from asset_dashboard.db.base import Base


def utcnow() -> datetime:
    """Naive UTC timestamp. SQLite has no real timezone-aware storage, so we
    standardize on naive-but-always-UTC datetimes everywhere to avoid
    aware/naive comparison bugs on read-back."""
    return datetime.now(UTC).replace(tzinfo=None)


def _now() -> datetime:
    return utcnow()


def _uuid() -> str:
    return str(uuid.uuid4())


class OperatorAccountStatus(enum.StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class OperatorAccountRole(enum.StrEnum):
    """Two-role model (feature 002): supersedes feature 001's single-role
    assumption. The first account on a fresh install becomes ADMINISTRATOR
    (FR-030); subsequent accounts default to OPERATOR."""

    ADMINISTRATOR = "administrator"
    OPERATOR = "operator"


class OperatorAccount(Base):
    """A local user who signs in (FR-001-FR-006).

    `password_hash` is Argon2id output ONLY — never plaintext/recoverable
    (FR-003). `failed_attempts`/`lock_until` back the sign-in throttle (FR-004).
    """

    __tablename__ = "operator_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[OperatorAccountRole] = mapped_column(
        Enum(OperatorAccountRole), default=OperatorAccountRole.OPERATOR
    )
    status: Mapped[OperatorAccountStatus] = mapped_column(
        Enum(OperatorAccountStatus), default=OperatorAccountStatus.ACTIVE
    )
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    lock_until: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=_now, onupdate=_now)


class AuditEventType(enum.StrEnum):
    SIGNIN_SUCCESS = "signin_success"
    SIGNIN_FAILURE = "signin_failure"
    LOCKOUT = "lockout"
    PROFILE_CHANGE = "profile_change"
    RUN_STARTED = "run_started"
    RUN_FINISHED = "run_finished"
    COMPLIANCE_CHECK = "compliance_check"
    SCHEDULE_CHANGE = "schedule_change"
    ACCOUNT_CHANGE = "account_change"
    ALLOWLIST_CHANGE = "allowlist_change"
    CONFIG_CHANGE = "config_change"
    TOOL_CHECK = "tool_check"


class AuditLogEntry(Base):
    """Append-only record of a security-relevant event (FR-006).

    `detail` MUST NEVER contain secrets (passwords, attempted default
    credentials) — see constitution Principle IV (Auditability) and
    FR-039. Credential-check detail may include attempt counts/timings
    for SC-008 verification, never the attempted secret itself.
    """

    __tablename__ = "audit_log_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    ts: Mapped[datetime] = mapped_column(DateTime(), default=_now, index=True)
    actor_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("operator_accounts.id"), nullable=True
    )
    event_type: Mapped[AuditEventType] = mapped_column(Enum(AuditEventType), index=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)

    actor: Mapped[OperatorAccount | None] = relationship()


class DiscoveryProfile(Base):
    """Reusable definition of what/how to discover (FR-007-FR-014, FR-042).

    `scan_params` MUST only ever contain allow-listed keys (enforced by
    profiles/validation.py before a row is written) — never raw nmap flags.
    `version_token` backs optimistic concurrency: a save against a stale
    token is rejected (FR-042), never silently overwritten.
    """

    __tablename__ = "discovery_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    target_scope: Mapped[list] = mapped_column(JSON, default=list)
    port_spec: Mapped[str] = mapped_column(String(256))
    scan_params: Mapped[dict] = mapped_column(JSON, default=dict)
    extracted_fields: Mapped[list] = mapped_column(JSON, default=list)
    selected_scripts: Mapped[list] = mapped_column(JSON, default=list)
    compliance_settings: Mapped[dict] = mapped_column(JSON, default=dict)
    cache_freshness_seconds: Mapped[int] = mapped_column(Integer, default=3600)
    version_token: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=_now, onupdate=_now)

    host_links: Mapped[list[HostLinkTemplate]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )


class HostLinkTemplate(Base):
    """URL template producing a per-host management link (FR-013, FR-019)."""

    __tablename__ = "host_link_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    profile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("discovery_profiles.id"), index=True
    )
    label: Mapped[str] = mapped_column(String(64), default="Manage")
    url_template: Mapped[str] = mapped_column(String(512))

    profile: Mapped[DiscoveryProfile] = relationship(back_populates="host_links")


class RunStatus(enum.StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class RunTrigger(enum.StrEnum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"


class DiscoveryRun(Base):
    """A persisted execution of a profile (FR-016-FR-023, FR-030, FR-043).

    `profile_snapshot` captures the profile's name + params as used at run
    time, so the run survives profile deletion (FR-027). At most one
    `running` row may exist per profile at a time (FR-043) — enforced by
    discovery/runner.py, not by a DB constraint alone.
    """

    __tablename__ = "discovery_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    profile_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("discovery_profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    profile_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    trigger: Mapped[RunTrigger] = mapped_column(Enum(RunTrigger), default=RunTrigger.MANUAL)
    triggered_by_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("operator_accounts.id"), nullable=True
    )
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus), default=RunStatus.RUNNING, index=True
    )
    served_from_cache: Mapped[bool] = mapped_column(default=False)
    source_run_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("discovery_runs.id"), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(), default=_now, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    params_used: Mapped[dict] = mapped_column(JSON, default=dict)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    error_detail: Mapped[str | None] = mapped_column(Text(), nullable=True)
    # Row-count-based archival (see archival.py) — distinct from the
    # existing per-profile retention (enforce_retention, which DELETES).
    # Archiving only hides a row from the default listing; it is never
    # deleted and `include_archived=true` still returns it.
    archived: Mapped[bool] = mapped_column(default=False, index=True)

    assets: Mapped[list[DiscoveredAsset]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class AssetState(enum.StrEnum):
    UP = "up"
    DOWN = "down"
    NO_RESPONSE = "no_response"


class DiscoveredAsset(Base):
    """A host found during a run (FR-018, FR-019)."""

    __tablename__ = "discovered_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("discovery_runs.id"), index=True)
    address: Mapped[str] = mapped_column(String(128))
    state: Mapped[AssetState] = mapped_column(Enum(AssetState), default=AssetState.UP)
    open_ports: Mapped[list] = mapped_column(JSON, default=list)
    extracted: Mapped[dict] = mapped_column(JSON, default=dict)
    management_link: Mapped[str | None] = mapped_column(String(512), nullable=True)

    run: Mapped[DiscoveryRun] = relationship(back_populates="assets")
    findings: Mapped[list[ComplianceFinding]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )


class ComplianceControl(enum.StrEnum):
    VERSION_VALIDITY = "version_validity"
    DEFAULT_CREDENTIALS = "default_credentials"


class ComplianceResult(enum.StrEnum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    UNKNOWN = "unknown"
    INCONCLUSIVE = "inconclusive"


class ComplianceFinding(Base):
    """Outcome of one control against one asset (FR-033-FR-039).

    `detail` MUST NEVER contain an attempted secret in recoverable form
    (FR-039) — only attempt counts/timings/matched-signature booleans.
    """

    __tablename__ = "compliance_findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("discovered_assets.id"), index=True
    )
    control: Mapped[ComplianceControl] = mapped_column(Enum(ComplianceControl))
    result: Mapped[ComplianceResult] = mapped_column(Enum(ComplianceResult))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    checked_at: Mapped[datetime] = mapped_column(DateTime(), default=_now)

    asset: Mapped[DiscoveredAsset] = relationship(back_populates="findings")


class OverlapPolicy(enum.StrEnum):
    SKIP = "skip"
    QUEUE = "queue"


class CatchUpPolicy(enum.StrEnum):
    RUN_ONCE = "run_once"
    SKIP = "skip"


class Schedule(Base):
    """Recurrence attached to a profile (FR-028-FR-032).

    `recurrence` is {"type": "interval", "seconds": N} or
    {"type": "daily", "hour": H, "minute": M} or
    {"type": "weekly", "day_of_week": 0-6, "hour": H, "minute": M}.
    """

    __tablename__ = "schedules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("discovery_profiles.id", ondelete="CASCADE"),
        index=True,
    )
    recurrence: Mapped[dict] = mapped_column(JSON, default=dict)
    target_scope: Mapped[list] = mapped_column(JSON, default=list)
    label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    enabled: Mapped[bool] = mapped_column(default=True)
    next_run_at: Mapped[datetime] = mapped_column(DateTime())
    overlap_policy: Mapped[OverlapPolicy] = mapped_column(
        Enum(OverlapPolicy), default=OverlapPolicy.SKIP
    )
    catch_up_policy: Mapped[CatchUpPolicy] = mapped_column(
        Enum(CatchUpPolicy), default=CatchUpPolicy.RUN_ONCE
    )
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=_now, index=True)
    # Row-count-based archival (see archival.py) — a schedule is never
    # deleted by archiving, only hidden from the default listing.
    archived: Mapped[bool] = mapped_column(default=False, index=True)

    profile: Mapped[DiscoveryProfile] = relationship()


class DeviceType(enum.StrEnum):
    """Common/suggested device-type values (V0.7 follow-up) — offered as
    `<datalist>` suggestions in the manual-entry UI (web/templates/
    _reference_versions.html), NOT an enforced enum: `type` is free-form
    classification text (real vendor catalogs need categories/sub-tracks
    — e.g. a UCM's separately versioned "System" vs "PBX" firmware — a
    small fixed list can't anticipate). It is never part of the
    compliance match key (a category string cannot be expected to appear
    in a scanned service/firmware banner string), which is why matching
    uses `vendor`(+`model`), not `type` (see compliance/version_check.py).

    The enum VALUE is the Ukrainian label stored/shown verbatim (not a
    separate code+label pair) — the UI's `<datalist>` inserts this text
    directly into the field, so there is exactly one piece of text per
    suggestion, not a technical code alongside a translation.
    """

    IP_PHONE = "IP-телефон"
    VOIP_GATEWAY = "VoIP-шлюз"
    SERVICE = "Сервіс"
    UCM = "АТС"
    SWITCH = "Комутатор"
    ROUTER = "Маршрутизатор"


class ReferenceVersionEntry(Base):
    """Locally maintained, offline minimum-version threshold (FR-005, FR-034,
    FR-035, FR-040; data-model.md §1 — V0.7 "Version Dictionary Overhaul").

    One effective threshold per `(vendor, model, type)`: a detected version
    below `min_version` is non-compliant, at/above is compliant, and no
    threshold on file is unknown. Evaluated with zero external/network
    lookup — see compliance/version_check.py. `type` is free-form
    classification text (see DeviceType) and plays no role in that
    matching (which uses `vendor`+`model` only) — it only disambiguates
    independently-versioned tracks on the same vendor/model during
    ingestion import (see version_ingestion/service.py).

    `version_match`/`status` are RETAINED as migration provenance only (the
    pre-V0.7 enumerated valid/invalid rows); new logic ignores them.
    """

    __tablename__ = "reference_version_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    vendor: Mapped[str] = mapped_column(String(128), index=True)
    type: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    min_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source: Mapped[str] = mapped_column(String(16), default="manual")  # "manual" | "ingested"
    source_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    needs_review: Mapped[bool] = mapped_column(default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=_now, onupdate=_now)
    version_match: Mapped[str | None] = mapped_column(String(128), nullable=True)  # legacy
    status: Mapped[str | None] = mapped_column(String(16), nullable=True)  # legacy
    note: Mapped[str | None] = mapped_column(Text(), nullable=True)


class VersionIngestionSource(Base):
    """Admin-tracked ingestion entry (FR-014; data-model.md §2).

    `source_url`/`extractor` are opaque configuration consumed by the
    out-of-runtime staging fetcher (`tools/version_fetcher/`) — this app only
    stores them, it never dereferences `source_url` itself.
    """

    __tablename__ = "version_ingestion_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    vendor: Mapped[str] = mapped_column(String(128), index=True)
    source_url: Mapped[str] = mapped_column(String(512))
    models: Mapped[list] = mapped_column(JSON, default=list)
    extractor: Mapped[dict] = mapped_column(JSON, default=dict)
    last_import_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    last_import_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    last_versions: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("operator_accounts.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=_now, onupdate=_now)


class DefaultCredentialEntry(Base):
    """Locally maintained, offline catalog of known factory-default vendor
    credentials (FR-036, FR-036a, FR-040).

    `credentials` holds {username, secret} pairs used in-memory only by the
    guarded credential check; the catalog itself is reference data, never a
    log of what was attempted (FR-039 governs the finding/audit side).
    `success_keywords` are matched against a response body to confirm a
    credential was accepted (FR-036a).
    """

    __tablename__ = "default_credential_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    vendor: Mapped[str] = mapped_column(String(128), index=True)
    service: Mapped[str] = mapped_column(String(16), index=True)  # sip|ssh|http|https|telnet|ftp|routeros-api
    credentials: Mapped[list] = mapped_column(JSON, default=list)  # [{"username", "secret"}, ...]
    success_keywords: Mapped[list] = mapped_column(JSON, default=list)
    # Feature 008: HTTP/HTTPS form-probe settings (login path, field names,
    # success/failure rules, optional fingerprint/CSRF). Empty `{}` ⇒ probe
    # defaults; ignored entirely by non-HTTP probes. See data-model.md §1.
    probe_config: Mapped[dict] = mapped_column(JSON, default=dict)


# ---------------------------------------------------------------------------
# Feature 002: NSE allow-list, admin-editable security settings, and the
# standalone credential tool + its scheduling.
# ---------------------------------------------------------------------------


class NseScriptAllowlistEntry(Base):
    """Curated, admin-editable list of selectable NSE scripts (FR-010-FR-018).

    The nmap command is still composed only from allow-listed entries at
    scan time (never a free-form `--script` string) — adding a non-"safe"
    entry here is a deliberate, audited, admin-only act (FR-016), not a
    weakening of that guarantee. Seeded from data/reference/nse_allowlist.json.
    """

    __tablename__ = "nse_script_allowlist_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    script_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    safety: Mapped[str] = mapped_column(String(16), default="safe")  # "safe" | "other"
    expected_ports: Mapped[list] = mapped_column(JSON, default=list)
    enabled: Mapped[bool] = mapped_column(default=True)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("operator_accounts.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=_now, onupdate=_now)


class SecuritySetting(Base):
    """A single admin-editable security setting, stored as a key/value row
    (FR-032). Unset keys fall back to config.py defaults — see
    settings_store/service.py. `password_min_length` can never be stored
    below the hard floor of 20.
    """

    __tablename__ = "security_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=_now, onupdate=_now)


class ToolType(enum.StrEnum):
    """Extensible for future standalone tools; only one exists today."""

    DEFAULT_CREDENTIALS = "default_credentials"


class ToolTask(Base):
    """A schedulable standalone-tool job, distinct from a profile `Schedule`
    (FR-020, FR-021). Scanned by the same shared scheduler (scheduling/engine.py)
    alongside `Schedule` rows.
    """

    __tablename__ = "tool_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tool: Mapped[ToolType] = mapped_column(Enum(ToolType), default=ToolType.DEFAULT_CREDENTIALS)
    target_scope: Mapped[list] = mapped_column(JSON, default=list)
    port: Mapped[int] = mapped_column(Integer)
    service: Mapped[str] = mapped_column(String(16))  # sip|ssh|http|https|telnet|ftp|routeros-api
    recurrence: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(default=True)
    next_run_at: Mapped[datetime] = mapped_column(DateTime())
    overlap_policy: Mapped[OverlapPolicy] = mapped_column(
        Enum(OverlapPolicy), default=OverlapPolicy.SKIP
    )
    catch_up_policy: Mapped[CatchUpPolicy] = mapped_column(
        Enum(CatchUpPolicy), default=CatchUpPolicy.RUN_ONCE
    )
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("operator_accounts.id"), nullable=True
    )
    # Feature 008: the chosen credential dictionary (US2) and the per-target
    # attempt ceiling (US4). `dictionary_id` null ⇒ all dictionaries for the
    # service (legacy). `attempt_ceiling` null ⇒ default = selected dictionary
    # size. ondelete=SET NULL so deleting a dictionary never breaks a task;
    # the app also nulls references defensively (mirrors the feature-007 fix).
    dictionary_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("default_credential_entries.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    attempt_ceiling: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ToolCheckRun(Base):
    """A persisted standalone credential-tool execution — on demand or
    scheduled (US5). Equivalent in shape/outcome regardless of trigger.
    """

    __tablename__ = "tool_check_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tool_task_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("tool_tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    trigger: Mapped[RunTrigger] = mapped_column(Enum(RunTrigger), default=RunTrigger.MANUAL)
    triggered_by_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("operator_accounts.id"), nullable=True
    )
    target_scope: Mapped[list] = mapped_column(JSON, default=list)
    port: Mapped[int] = mapped_column(Integer)
    service: Mapped[str] = mapped_column(String(16))
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus), default=RunStatus.RUNNING, index=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(), default=_now, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    # Feature 008: the dictionary used (snapshotted by id) and the effective
    # attempt ceiling recorded for this run; `error_detail` is set when a
    # background run fails (FR-117), mirroring DiscoveryRun.error_detail.
    dictionary_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("default_credential_entries.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    attempt_ceiling: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text(), nullable=True)
    # Row-count-based archival (see archival.py) — never deleted, just
    # hidden from the default listing.
    archived: Mapped[bool] = mapped_column(default=False, index=True)

    results: Mapped[list[ToolCheckResult]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class ToolCheckResult(Base):
    """Per-target outcome within a ToolCheckRun (device-safety counts
    only; `detail` NEVER holds a secret, FR-024)."""

    __tablename__ = "tool_check_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("tool_check_runs.id"), index=True)
    address: Mapped[str] = mapped_column(String(128))
    result: Mapped[ComplianceResult] = mapped_column(Enum(ComplianceResult))
    attempts_made: Mapped[int] = mapped_column(Integer, default=0)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)

    run: Mapped[ToolCheckRun] = relationship(back_populates="results")

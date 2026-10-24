"""Wire the version-validity check into a discovered asset (FR-033).

Called once per responding asset, after it is persisted, when the
profile's `compliance_settings` enables the control.

Feature 002 (FR-020): the default-credential check is decoupled from
discovery-profile runs entirely — it is now a standalone tool
(tools/credential_tool/) that runs on demand or on its own schedule via
`check_default_credentials` directly. A profile's `compliance_settings`
no longer has any effect on it, even if a legacy payload still sets
`default_credentials` (silently ignored here).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from asset_dashboard.compliance.version_check import check_version
from asset_dashboard.db.models import (
    ComplianceControl,
    ComplianceFinding,
    ComplianceResult,
    DiscoveredAsset,
)

_VERSION_RESULT_MAP = {
    "compliant": ComplianceResult.COMPLIANT,
    "non_compliant": ComplianceResult.NON_COMPLIANT,
    "unknown": ComplianceResult.UNKNOWN,
}


def evaluate_asset_compliance(
    session: Session,
    asset: DiscoveredAsset,
    open_ports: list[dict],
    compliance_settings: dict,
) -> None:
    if compliance_settings.get("version_validity"):
        version_string = asset.extracted.get("service_version")
        status, detail = check_version(session, version_string)
        session.add(
            ComplianceFinding(
                asset_id=asset.id,
                control=ComplianceControl.VERSION_VALIDITY,
                result=_VERSION_RESULT_MAP[status],
                detail=detail,
            )
        )

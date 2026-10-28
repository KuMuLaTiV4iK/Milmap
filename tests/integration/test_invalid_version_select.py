"""Integration test for User Story 4 (feature 009): auto-select hosts whose
version-validity result is non_compliant.

- run_detail annotates each host row with its version-validity result
  (non_compliant / unknown / compliant) via data-version-result;
- the "Select invalid-version hosts" control is present on a version-evaluated
  run, and the data attributes that drive it are present only for evaluated
  runs — a run without version-validity findings carries no annotation, so the
  control is disabled client-side (FR-003, FR-004, SC-003).
"""

from asset_dashboard.db.base import session_scope
from asset_dashboard.db.models import (
    ComplianceControl,
    ComplianceFinding,
    ComplianceResult,
    DiscoveredAsset,
    DiscoveryRun,
    RunStatus,
)


def _make_run(*, findings_by_address):
    """Create a completed run with one asset per address; each address maps to
    a version-validity result string, or None for no finding at all."""
    with session_scope() as session:
        run = DiscoveryRun(
            profile_snapshot={"name": "US4 run"},
            status=RunStatus.COMPLETED,
            params_used={"target_scope": list(findings_by_address)},
            summary={"hosts": len(findings_by_address), "ports_in_results": 0},
        )
        session.add(run)
        session.flush()
        for address, result in findings_by_address.items():
            asset = DiscoveredAsset(run_id=run.id, address=address, open_ports=[], extracted={})
            session.add(asset)
            session.flush()
            if result is not None:
                session.add(
                    ComplianceFinding(
                        asset_id=asset.id,
                        control=ComplianceControl.VERSION_VALIDITY,
                        result=ComplianceResult(result),
                        detail={},
                    )
                )
        return run.id


def test_rows_annotated_with_version_result_and_control_present(authed_client):
    run_id = _make_run(
        findings_by_address={
            "10.0.0.1": "non_compliant",
            "10.0.0.2": "compliant",
            "10.0.0.3": "unknown",
        }
    )
    page = authed_client.get(f"/runs/{run_id}", headers={"accept": "text/html"})
    assert page.status_code == 200
    # Each row carries its version-validity result.
    assert 'data-version-result="non_compliant"' in page.text
    assert 'data-version-result="compliant"' in page.text
    assert 'data-version-result="unknown"' in page.text
    # The auto-select control is rendered.
    assert "Вибрати хости з недійсною версією" in page.text  # run.select_invalid_version
    assert "select-invalid-version-btn" in page.text
    # The union-select JS only ticks non_compliant rows.
    assert "data-version-result') === 'non_compliant'" in page.text


def test_non_version_evaluated_run_has_no_annotations(authed_client):
    run_id = _make_run(findings_by_address={"10.0.0.9": None, "10.0.0.10": None})
    page = authed_client.get(f"/runs/{run_id}", headers={"accept": "text/html"})
    assert page.status_code == 200
    # No version-validity annotation ⇒ the control disables itself client-side.
    assert "data-version-result" not in _rows_only(page.text)
    # The button is still present (disabled is applied by initInvalidVersionButton).
    assert "select-invalid-version-btn" in page.text


def _rows_only(html):
    """Only the <tbody> region, so the JS's own 'data-version-result' string
    literal in the page script does not count as a row annotation."""
    start = html.find("<tbody>")
    end = html.find("</tbody>")
    return html[start:end] if start >= 0 and end >= 0 else html

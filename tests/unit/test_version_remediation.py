"""FR-007: on a below-threshold match, `check_version` attaches
`expected_valid` as the threshold's upgrade target; on no threshold, no
`expected_valid` key is present — never an invented version."""
from asset_dashboard.compliance.version_check import check_version
from asset_dashboard.db.base import session_scope
from asset_dashboard.db.models import ReferenceVersionEntry


def test_below_threshold_attaches_expected_valid_upgrade_target(client):
    with session_scope() as session:
        session.add(
            ReferenceVersionEntry(
                vendor="OpenSSH",
                type="router",
                min_version="9.0",
                note="End-of-life branch",
            )
        )

    with session_scope() as session:
        result, detail = check_version(session, "OpenSSH 7.4")

    assert result == "non_compliant"
    assert detail["expected_valid"] == "OpenSSH 9.0"
    assert detail["note"] == "End-of-life branch"


def test_no_threshold_on_file_carries_no_expected_valid_key(client):
    with session_scope() as session:
        result, detail = check_version(session, "LegacyFirmware 1.0")

    assert result == "unknown"
    assert "expected_valid" not in detail


def test_compliant_match_still_carries_expected_valid_as_its_own_threshold(client):
    with session_scope() as session:
        session.add(
            ReferenceVersionEntry(vendor="OpenSSH", type="router", min_version="9.0")
        )

    with session_scope() as session:
        result, detail = check_version(session, "OpenSSH 9.2")

    assert result == "compliant"
    assert detail["expected_valid"] == "OpenSSH 9.0"

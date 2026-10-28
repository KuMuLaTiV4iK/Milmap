"""Unit tests for the minimum-version threshold check (FR-001-FR-008):
below/equal/above threshold, no-threshold, unorderable detected version,
and zero network calls."""

import socket

from asset_dashboard.compliance.version_check import check_version
from asset_dashboard.db.base import session_scope
from asset_dashboard.db.models import ReferenceVersionEntry


def test_below_threshold_is_non_compliant(client):
    with session_scope() as session:
        session.add(ReferenceVersionEntry(vendor="OpenSSH", type="router", min_version="9.0"))

    with session_scope() as session:
        result, detail = check_version(session, "OpenSSH 7.4")

    assert result == "non_compliant"
    assert detail["checked_version"] == "7.4"
    assert detail["threshold"] == "9.0"
    assert detail["comparison"] == "below_threshold"
    assert detail["expected_valid"] == "OpenSSH 9.0"


def test_at_threshold_is_compliant(client):
    with session_scope() as session:
        session.add(ReferenceVersionEntry(vendor="OpenSSH", type="router", min_version="9.0"))

    with session_scope() as session:
        result, detail = check_version(session, "OpenSSH 9.0")

    assert result == "compliant"
    assert detail["comparison"] == "at_or_above"


def test_above_threshold_is_compliant(client):
    with session_scope() as session:
        session.add(ReferenceVersionEntry(vendor="OpenSSH", type="router", min_version="9.0"))

    with session_scope() as session:
        result, _detail = check_version(session, "OpenSSH 9.2")

    assert result == "compliant"


def test_no_threshold_on_file_is_unknown(client):
    with session_scope() as session:
        result, detail = check_version(session, "Acme Widget 1.0")

    assert result == "unknown"
    assert detail["comparison"] == "no_threshold"


def test_unorderable_detected_version_is_unknown(client):
    with session_scope() as session:
        session.add(ReferenceVersionEntry(vendor="OpenSSH", type="router", min_version="9.0"))

    with session_scope() as session:
        result, detail = check_version(session, "OpenSSH not-a-version")

    assert result == "unknown"
    assert detail["comparison"] == "not_comparable"


def test_missing_version_string_is_unknown(client):
    with session_scope() as session:
        result, _detail = check_version(session, None)

    assert result == "unknown"


def test_check_version_makes_zero_network_calls():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from asset_dashboard.db.base import Base
    from asset_dashboard.db.models import ReferenceVersionEntry  # noqa: F401

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(ReferenceVersionEntry(vendor="OpenSSH", type="router", min_version="9.0"))
    session.commit()

    real_socket = socket.socket
    real_create_connection = socket.create_connection

    def _forbidden(*args, **kwargs):
        raise AssertionError("check_version must never open a network socket")

    socket.socket = _forbidden
    socket.create_connection = _forbidden
    try:
        result, _detail = check_version(session, "OpenSSH 7.4")
    finally:
        socket.socket = real_socket
        socket.create_connection = real_create_connection
        session.close()
        engine.dispose()

    assert result == "non_compliant"

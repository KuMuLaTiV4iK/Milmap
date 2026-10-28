"""FR-003a: `validate_target_scope`/`validate_profile` allow an empty
target when `require_target=False`, while a present-but-invalid target is
still fully validated either way."""

from asset_dashboard.profiles.validation import validate_profile, validate_target_scope


def test_empty_target_scope_valid_when_require_target_false():
    assert validate_target_scope([], require_target=False) is None


def test_empty_target_scope_invalid_by_default():
    assert validate_target_scope([]) is not None


def test_non_empty_invalid_target_rejected_even_when_require_target_false():
    assert validate_target_scope(["not-a-target!!"], require_target=False) is not None


def test_non_empty_valid_target_accepted_when_require_target_false():
    assert validate_target_scope(["10.0.0.0/24"], require_target=False) is None


def test_validate_profile_allows_empty_target_when_require_target_false():
    payload = {
        "name": "Target-less profile",
        "target_scope": [],
        "port_spec": "22",
        "scan_params": {"timing": "T3"},
        "extracted_fields": [],
    }
    assert validate_profile(payload, require_target=False) == {}


def test_validate_profile_still_rejects_empty_target_by_default():
    payload = {
        "name": "Needs a target",
        "target_scope": [],
        "port_spec": "22",
        "scan_params": {"timing": "T3"},
        "extracted_fields": [],
    }
    errors = validate_profile(payload)
    assert "target_scope" in errors


def test_validate_profile_rejects_invalid_present_target_even_when_require_target_false():
    payload = {
        "name": "Bad target",
        "target_scope": ["not-a-target!!"],
        "port_spec": "22",
        "scan_params": {"timing": "T3"},
        "extracted_fields": [],
    }
    errors = validate_profile(payload, require_target=False)
    assert "target_scope" in errors

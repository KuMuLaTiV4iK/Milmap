"""Unit tests for the deterministic SemVer-style comparator (FR-006,
research D1): `compliance/version_compare.py`."""

from asset_dashboard.compliance.version_compare import (
    compare_versions,
    normalize_wildcard_floor,
)


def test_missing_trailing_segment_is_treated_as_zero():
    assert compare_versions("9.0", "9.0.0") == 0


def test_prerelease_suffix_sorts_below_same_base_release():
    assert compare_versions("9.0-rc1", "9.0") == -1
    assert compare_versions("9.0", "9.0-rc1") == 1


def test_numeric_segment_comparison_is_not_lexical():
    assert compare_versions("9.10", "9.9") == 1
    assert compare_versions("9.9", "9.10") == -1


def test_equal_versions_compare_equal():
    assert compare_versions("1.2.3", "1.2.3") == 0


def test_mixed_scheme_or_garbage_is_not_comparable():
    assert compare_versions("abc", "9.0") is None
    assert compare_versions("9.0", "not-a-version") is None
    assert compare_versions("", "9.0") is None


def test_normalize_wildcard_floor():
    assert normalize_wildcard_floor("9.*") == "9.0"
    assert normalize_wildcard_floor("9.0") == "9.0"
    assert normalize_wildcard_floor("*") == "0"

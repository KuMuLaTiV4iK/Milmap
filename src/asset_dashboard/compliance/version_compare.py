"""Deterministic SemVer-style version comparator (FR-006, research D1).

Pure, offline, in-memory comparison — no network, no external dependency.
Split each version on `.`; compare numeric segments left-to-right; missing
trailing segments are treated as `0` (`9.0` == `9.0.0`). A pre-release/
suffix (anything after a non-numeric boundary, e.g. `-rc1`, `b2`) sorts
BELOW the same base release (`9.0-rc1` < `9.0`). If either side is not
orderable by this rule, or the two use mismatched schemes, comparison
signals "not comparable" (`None`) — callers must treat that as `unknown`,
never a guessed verdict.
"""
from __future__ import annotations

import re

_SEGMENT_RE = re.compile(r"^(\d+)(.*)$")


class ParsedVersion:
    """A version split into numeric release segments plus an optional
    pre-release/suffix string taken from the first segment that isn't a
    clean integer."""

    __slots__ = ("segments", "suffix")

    def __init__(self, segments: tuple[int, ...], suffix: str | None) -> None:
        self.segments = segments
        self.suffix = suffix


def parse_version(version_string: str) -> ParsedVersion | None:
    """Parse a version string, or return None if it is not orderable by
    this comparator's rules (e.g. empty, non-numeric scheme)."""
    if not version_string:
        return None
    text = version_string.strip()
    if not text:
        return None

    parts = text.split(".")
    segments: list[int] = []
    suffix: str | None = None

    for i, part in enumerate(parts):
        match = _SEGMENT_RE.match(part)
        if match is None:
            # Non-numeric from the start of this segment: not orderable.
            return None
        number_str, rest = match.groups()
        segments.append(int(number_str))
        if rest:
            # Anything trailing a numeric segment (e.g. "0-rc1", "2b") is the
            # pre-release/suffix marker; it must be the last `.`-segment.
            suffix = rest
            if i != len(parts) - 1:
                return None
            break

    if not segments:
        return None
    return ParsedVersion(tuple(segments), suffix)


def compare_versions(left: str, right: str) -> int | None:
    """Return -1/0/1 if `left` is less/equal/greater than `right`, or None
    if the two are not comparable (unorderable or mismatched schemes)."""
    parsed_left = parse_version(left)
    parsed_right = parse_version(right)
    if parsed_left is None or parsed_right is None:
        return None

    max_len = max(len(parsed_left.segments), len(parsed_right.segments))
    left_segments = parsed_left.segments + (0,) * (max_len - len(parsed_left.segments))
    right_segments = parsed_right.segments + (0,) * (max_len - len(parsed_right.segments))

    if left_segments != right_segments:
        return -1 if left_segments < right_segments else 1

    # Equal base release: a suffix (pre-release) sorts below no-suffix.
    if parsed_left.suffix == parsed_right.suffix:
        return 0
    if parsed_left.suffix is None:
        return 1
    if parsed_right.suffix is None:
        return -1
    # Both have a suffix on an equal base release: compare lexically as a
    # deterministic, documented tie-break (no further semantics assumed).
    return -1 if parsed_left.suffix < parsed_right.suffix else 1


def normalize_wildcard_floor(version_string: str) -> str:
    """Normalize a wildcard-style floor expression (e.g. `9.*`) to its
    lowest concrete version (`9.0`), per research D3. Non-wildcard inputs
    are returned unchanged."""
    if version_string.endswith(".*"):
        return version_string[: -len(".*")] + ".0"
    if version_string == "*":
        return "0"
    return version_string

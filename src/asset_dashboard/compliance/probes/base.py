"""Shared contract for default-credential probes (FR-036, FR-036a).

Each probe performs exactly ONE network authentication attempt per call —
no internal retry/looping. The attempt-count and cooldown invariants
(constitution Principle III, NON-NEGOTIABLE) are enforced centrally by
compliance/credential_check.py, never inside an individual probe, so
every protocol inherits identical safety limits.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ProbeAttemptResult:
    matched: bool
    # For operator debugging only. MUST NEVER include the attempted secret
    # (FR-039) — callers populate this from the response body alone.
    response_excerpt: str
    # Feature 008: protocol status/code shown in the per-attempt result row
    # (e.g. HTTP 401). Non-HTTP probes leave it None (the result table shows
    # a protocol label instead). Still body-only/secret-free overall.
    status: int | None = None


def body_matches_success(response_body: str, success_keywords: list[str]) -> bool:
    """FR-036a: confirmation is a keyword/signature match against the
    response BODY, not merely a protocol-level status code."""
    if not response_body or not success_keywords:
        return False
    lowered = response_body.lower()
    return any(keyword.lower() in lowered for keyword in success_keywords)

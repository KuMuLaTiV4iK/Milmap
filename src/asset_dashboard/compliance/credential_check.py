"""Central guarded default-credential check (FR-036-FR-039, feature 008).

NON-NEGOTIABLE device-safety invariant (constitution Principle III,
v2.0.0): at least `settings.credential_check_cooldown_seconds` between
consecutive authentication attempts per target. This is enforced HERE,
centrally — never inside an individual protocol probe — so every probe
inherits the identical cooldown and the invariant can be tested and
audited in one place.

The attempt *ceiling* is now operator-configurable (feature 008): by
default it equals the number of candidate credentials in the chosen
dictionary (so an operator can exhaustively audit it), and a configured
ceiling BELOW the dictionary size is the only thing that yields an
`inconclusive` result. The check stops on the first match.

Candidate credentials come from the locally maintained, offline
DefaultCredentialEntry catalog, optionally scoped to one dictionary.
Attempted secrets are held only in memory for the duration of a single
probe call and are never written to the resulting finding or the audit
log (FR-039/FR-114) — only usernames, attempt counts, a protocol label,
a status code and a body-only excerpt are recorded.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from asset_dashboard.compliance.probes import ftp as ftp_probe
from asset_dashboard.compliance.probes import http as http_probe
from asset_dashboard.compliance.probes import routeros_api as routeros_api_probe
from asset_dashboard.compliance.probes import sip as sip_probe
from asset_dashboard.compliance.probes import ssh as ssh_probe
from asset_dashboard.compliance.probes import telnet as telnet_probe
from asset_dashboard.config import settings
from asset_dashboard.db.models import DefaultCredentialEntry


def _https_attempt(host, port, username, secret, success_keywords, *, probe_config=None):
    """HTTPS is the HTTP probe over TLS (self-signed tolerated, feature 008)."""
    return http_probe.attempt(
        host, port, username, secret, success_keywords, scheme="https", probe_config=probe_config
    )


_PROBES = {
    "sip": sip_probe.attempt,
    "ssh": ssh_probe.attempt,
    "http": http_probe.attempt,
    "https": _https_attempt,
    "telnet": telnet_probe.attempt,
    "ftp": ftp_probe.attempt,
    "routeros-api": routeros_api_probe.attempt,
}

# Only these probes understand the dictionary's HTTP form `probe_config`;
# every other probe keeps the five-positional-arg signature unchanged.
_HTTP_SERVICES = {"http", "https"}


@dataclass
class CredentialCheckResult:
    result: str  # "compliant" | "non_compliant" | "inconclusive"
    attempts_made: int
    protocol: str
    matched_username: str | None = None
    matched_dictionary_entry: str | None = None
    # Per-attempt rows, password-free (FR-114): {username, status, excerpt, matched}.
    attempts: list[dict] = field(default_factory=list)


def _call_probe(service, probe_fn, host, port, username, secret, success_keywords, probe_config):
    """Dispatch one probe call, passing `probe_config` only to HTTP/HTTPS."""
    if service in _HTTP_SERVICES:
        return probe_fn(host, port, username, secret, success_keywords, probe_config=probe_config)
    return probe_fn(host, port, username, secret, success_keywords)


def check_default_credentials(
    session: Session,
    host: str,
    port: int,
    service: str,
    *,
    sleep_fn=None,
    dictionary_id: str | None = None,
    ceiling: int | None = None,
    attempt_sink: Callable[[dict], None] | None = None,
) -> CredentialCheckResult:
    """Attempt known default credentials for `service` against `host:port`.

    `dictionary_id` scopes the candidates to a single DefaultCredentialEntry
    (feature 008, US2); `None` falls back to every dictionary for the
    service (legacy behavior). `ceiling` caps attempts per target; `None`
    means "the whole chosen dictionary" (= number of candidates). The
    non-negotiable >=5s cooldown is always honored between consecutive
    attempts. `sleep_fn` is injectable so tests can assert the cooldown
    without a real multi-second wait. Each attempt is appended to the
    result's `attempts` list and, if given, handed to `attempt_sink`.
    """
    # Resolve `time.sleep` at call time (not as a default-arg value bound at
    # import) so a monkeypatch of this module's `time.sleep` is honored on
    # the background-worker path too.
    sleep = sleep_fn if sleep_fn is not None else time.sleep

    probe_fn = _PROBES.get(service)
    if probe_fn is None:
        return CredentialCheckResult(result="inconclusive", attempts_made=0, protocol=service)

    query = session.query(DefaultCredentialEntry).filter_by(service=service)
    if dictionary_id is not None:
        query = query.filter(DefaultCredentialEntry.id == dictionary_id)
    entries = query.all()
    candidates: list[tuple[str, str, list[str], dict, str]] = [
        (
            cred["username"],
            cred["secret"],
            entry.success_keywords,
            entry.probe_config or {},
            entry.id,
        )
        for entry in entries
        for cred in entry.credentials
    ]

    cooldown = settings.credential_check_cooldown_seconds
    # Default ceiling = whole dictionary (exhaustive audit, constitution
    # v2.0.0). A configured ceiling can only lower it.
    effective_ceiling = ceiling if ceiling is not None else len(candidates)

    attempts: list[dict] = []
    attempts_made = 0
    for username, secret, success_keywords, probe_config, entry_id in candidates:
        if attempts_made >= effective_ceiling:
            break
        if attempts_made > 0:
            sleep(cooldown)  # the NON-NEGOTIABLE cooldown between attempts

        attempts_made += 1
        outcome = _call_probe(
            service, probe_fn, host, port, username, secret, success_keywords, probe_config
        )
        row = {
            "username": username,
            "status": outcome.status,
            "excerpt": outcome.response_excerpt,
            "matched": outcome.matched,
        }
        attempts.append(row)
        if attempt_sink is not None:
            attempt_sink(row)
        if outcome.matched:
            # Stop on first match (constitution v2.0.0): never keep trying.
            return CredentialCheckResult(
                result="non_compliant",
                attempts_made=attempts_made,
                protocol=service,
                matched_username=username,
                matched_dictionary_entry=entry_id,
                attempts=attempts,
            )

    # No match. A configured ceiling that stopped us BELOW the dictionary
    # size is the only inconclusive path (FR-111); otherwise every candidate
    # was tried and the target is compliant (FR-110).
    stopped_below_dictionary = effective_ceiling < len(candidates)
    result = "inconclusive" if stopped_below_dictionary else "compliant"
    return CredentialCheckResult(
        result=result, attempts_made=attempts_made, protocol=service, attempts=attempts
    )

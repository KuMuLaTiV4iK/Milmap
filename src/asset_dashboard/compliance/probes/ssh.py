"""SSH default-credential probe (FR-036-FR-039).

One connection attempt per call, confirmed by matching the post-auth
banner/output against the configured success keywords (FR-036a) — never
by the mere absence of an AuthenticationException alone.
"""

from __future__ import annotations

import paramiko

from asset_dashboard.compliance.probes.base import ProbeAttemptResult, body_matches_success


def attempt(
    host: str,
    port: int,
    username: str,
    secret: str,
    success_keywords: list[str],
    timeout: float = 5.0,
) -> ProbeAttemptResult:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    body = ""
    try:
        client.connect(
            host,
            port=port,
            username=username,
            password=secret,
            timeout=timeout,
            banner_timeout=timeout,
            auth_timeout=timeout,
            look_for_keys=False,
            allow_agent=False,
        )
        transport = client.get_transport()
        body = transport.remote_version if transport else ""
        try:
            _stdin, stdout, _stderr = client.exec_command(
                "echo asset-dashboard-audit", timeout=timeout
            )
            body += stdout.read().decode(errors="replace")
        except (paramiko.SSHException, OSError):
            pass
    except (paramiko.AuthenticationException, paramiko.SSHException, OSError):
        body = ""
    finally:
        client.close()

    return ProbeAttemptResult(
        matched=body_matches_success(body, success_keywords), response_excerpt=body[:200]
    )

"""FTP default-credential probe (FR-036-FR-039).

One login attempt per call. A successful login returns the server's
`230`-class response which, with the connect banner, forms the response
body matched against the configured success keywords (FR-036a). A rejected
login raises inside ftplib and yields an empty body (no match), so
compliance is never inferred from a bare protocol success alone.
"""

from __future__ import annotations

import ftplib

from asset_dashboard.compliance.probes.base import ProbeAttemptResult, body_matches_success


def attempt(
    host: str,
    port: int,
    username: str,
    secret: str,
    success_keywords: list[str],
    timeout: float = 5.0,
) -> ProbeAttemptResult:
    body = ""
    ftp = ftplib.FTP()
    try:
        ftp.connect(host, port, timeout=timeout)
        welcome = ftp.getwelcome() or ""
        login_response = ftp.login(username, secret)  # raises on bad credentials
        body = f"{welcome}\n{login_response}"
    except ftplib.all_errors:
        body = ""
    finally:
        try:
            ftp.close()
        except OSError:
            pass

    return ProbeAttemptResult(
        matched=body_matches_success(body, success_keywords), response_excerpt=body[:200]
    )

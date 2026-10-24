"""Telnet default-credential probe (FR-036-FR-039).

Python 3.13+ removed the stdlib `telnetlib`, and its async-only
replacement (`telnetlib3`) would mix awkwardly with this otherwise
synchronous probe set — so this performs a minimal raw-socket login
exchange instead (research.md's documented fallback).
"""
from __future__ import annotations

import socket
import time

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
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            _best_effort_recv(sock)  # consume the login prompt
            sock.sendall((username + "\r\n").encode())
            time.sleep(0.2)
            _best_effort_recv(sock)  # consume the password prompt
            sock.sendall((secret + "\r\n").encode())
            time.sleep(0.3)
            body = _best_effort_recv(sock)
    except OSError:
        body = ""

    return ProbeAttemptResult(
        matched=body_matches_success(body, success_keywords), response_excerpt=body[:200]
    )


def _best_effort_recv(sock: socket.socket, size: int = 4096) -> str:
    try:
        return sock.recv(size).decode(errors="replace")
    except OSError:
        return ""

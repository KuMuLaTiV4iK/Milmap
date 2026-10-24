"""RouterOS API (MikroTik, TCP 8728) default-credential probe (FR-036-FR-039).

One login attempt per call over MikroTik's binary API protocol, using the
post-6.43 plain `/login` (name + password in a single sentence). The device
replies with `!done` on success or `!trap` (plus a message) on a rejected
login — a definitive body signature, matched here rather than a bare TCP
connect (FR-036a). The attempted secret is only ever sent, never echoed in
the reply, so it cannot leak into the recorded excerpt (FR-039).
"""
from __future__ import annotations

import socket

from asset_dashboard.compliance.probes.base import ProbeAttemptResult, body_matches_success


def _encode_length(length: int) -> bytes:
    """MikroTik API variable-length word-length prefix."""
    if length < 0x80:
        return bytes([length])
    if length < 0x4000:
        length |= 0x8000
        return bytes([(length >> 8) & 0xFF, length & 0xFF])
    if length < 0x200000:
        length |= 0xC00000
        return bytes([(length >> 16) & 0xFF, (length >> 8) & 0xFF, length & 0xFF])
    if length < 0x10000000:
        length |= 0xE0000000
        return bytes(
            [(length >> 24) & 0xFF, (length >> 16) & 0xFF, (length >> 8) & 0xFF, length & 0xFF]
        )
    return bytes(
        [0xF0, (length >> 24) & 0xFF, (length >> 16) & 0xFF, (length >> 8) & 0xFF, length & 0xFF]
    )


def _send_sentence(sock: socket.socket, words: list[str]) -> None:
    payload = b""
    for word in words:
        encoded = word.encode()
        payload += _encode_length(len(encoded)) + encoded
    payload += b"\x00"  # a zero-length word terminates the sentence
    sock.sendall(payload)


def _read_reply(sock: socket.socket) -> str:
    chunks: list[bytes] = []
    try:
        while True:
            data = sock.recv(4096)
            if not data:
                break
            chunks.append(data)
            joined = b"".join(chunks)
            if b"!done" in joined or b"!trap" in joined or b"!fatal" in joined:
                break
    except OSError:
        pass
    # latin-1 so arbitrary length-prefix bytes never raise; the API reply
    # words (!done/!trap/=message=...) are plain ASCII either way.
    return b"".join(chunks).decode("latin-1", errors="replace")


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
            _send_sentence(sock, ["/login", f"=name={username}", f"=password={secret}"])
            body = _read_reply(sock)
    except OSError:
        body = ""

    # A RouterOS login succeeds iff the reply carries `!done` without a
    # preceding `!trap`/`!fatal`. When the catalog also supplies success
    # keywords, require them too; otherwise the protocol signal stands alone.
    login_ok = "!done" in body and "!trap" not in body and "!fatal" not in body
    matched = login_ok and (not success_keywords or body_matches_success(body, success_keywords))

    return ProbeAttemptResult(matched=matched, response_excerpt=body[:200])

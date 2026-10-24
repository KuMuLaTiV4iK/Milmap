"""Orchestrate the `nmap` subprocess (FR-015).

Only allow-listed scan_params (already validated by profiles/validation.py
before a profile is ever saved) are translated into nmap flags — this
function never accepts or forwards a raw/free-form flag string, which is
the command-injection guard described in research.md.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass

DEFAULT_TIMING = "T3"  # FR-001: new profiles default to T3 when unspecified.


class NmapNotAvailableError(RuntimeError):
    """Raised when the nmap binary is missing or not executable (FR-020)."""


@dataclass
class NmapRunHandle:
    process: subprocess.Popen
    command: list[str]

    def cancel(self) -> None:
        """Terminate the running scan; retained partial results stay on disk/stdout
        up to the point of cancellation (FR-017 is enforced by the caller, which
        reads whatever stdout was captured before cancel)."""
        if self.process.poll() is not None:
            return
        try:
            if sys.platform == "win32":
                self.process.terminate()
            else:
                self.process.terminate()
        except OSError:
            pass


def build_nmap_command(
    target_scope: list[str],
    port_spec: str,
    scan_params: dict,
    extracted_fields: list[str] | None = None,
    selected_scripts: list[str] | None = None,
) -> list[str]:
    """Translate a validated profile into an nmap command line (FR-001, FR-005-FR-010).

    `scan_params`/`extracted_fields`/`selected_scripts` MUST already be
    allow-list-validated (profiles/validation.py, nse/allowlist.py) before
    reaching this function — this is the one place a profile becomes an
    actual command line, and it never accepts a raw/free-form flag string.

    Timing defaults to T3 when the profile doesn't specify one (FR-001).
    `-sV` is emitted iff `service_version` is in `extracted_fields` — there
    is no separate "service_detection" toggle (collapsed per research.md §3).
    A single `--script <comma-joined ids>` is appended for `selected_scripts`.
    """
    command = ["nmap", "-oX", "-", "-p", port_spec]

    timing = scan_params.get("timing") or DEFAULT_TIMING
    command.append(f"-{timing}")

    if extracted_fields and "service_version" in extracted_fields:
        command.append("-sV")

    intensity = scan_params.get("service_version_intensity")
    if intensity is not None:
        command.extend(["--version-intensity", str(intensity)])

    max_rate = scan_params.get("max_rate")
    if max_rate is not None:
        command.extend(["--max-rate", str(max_rate)])

    host_timeout = scan_params.get("host_timeout_seconds")
    if host_timeout is not None:
        command.extend(["--host-timeout", f"{host_timeout}s"])

    if scan_params.get("skip_host_discovery"):
        command.append("-Pn")

    if selected_scripts:
        command.extend(["--script", ",".join(selected_scripts)])

    command.extend(target_scope)
    return command


def is_nmap_available() -> bool:
    return shutil.which("nmap") is not None


def start_nmap(
    target_scope: list[str],
    port_spec: str,
    scan_params: dict,
    extracted_fields: list[str] | None = None,
    selected_scripts: list[str] | None = None,
) -> NmapRunHandle:
    if not is_nmap_available():
        raise NmapNotAvailableError(
            "nmap is not installed or not on PATH. Install nmap on this host "
            "with sufficient privileges for the configured scan types."
        )

    command = build_nmap_command(
        target_scope, port_spec, scan_params, extracted_fields, selected_scripts
    )
    process = subprocess.Popen(  # noqa: S603 - command built from a validated allow-list, never raw user input
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return NmapRunHandle(process=process, command=command)


def wait_for_result(handle: NmapRunHandle) -> tuple[str, str, int]:
    """Block until the process exits; return (stdout_xml, stderr, returncode)."""
    stdout, stderr = handle.process.communicate()
    return stdout, stderr, handle.process.returncode

"""Profile validation (FR-001, FR-005-FR-013).

Scan parameters are restricted to an explicit allow-list — raw/free-form
nmap flags are rejected outright. This both optimizes discovery time (only
vetted, bounded tunables are exposed) and prevents command injection, since
no user-supplied string ever reaches the nmap command line unvalidated.

Feature 002: `extracted_fields` no longer has a forced minimum (any subset
of ALLOWED_EXTRACTED_FIELDS, including empty, is valid — FR-005/FR-006);
the host-management-link capability is removed from profiles (FR-004) —
`validate_host_link_templates` is gone and any `host_links` sent by a
client is ignored, never validated.
"""

from __future__ import annotations

import ipaddress
import re

ALLOWED_TIMING_TEMPLATES = {"T0", "T1", "T2", "T3", "T4", "T5"}
DEFAULT_TIMING_TEMPLATE = "T3"
ALLOWED_SCAN_PARAM_KEYS = {
    "timing",  # one of ALLOWED_TIMING_TEMPLATES -> nmap -T0..-T5
    "service_version_intensity",  # 0-9 -> nmap --version-intensity
    "max_rate",  # positive int -> nmap --max-rate
    "host_timeout_seconds",  # positive int -> nmap --host-timeout
    "skip_host_discovery",  # bool -> nmap -Pn
}

ALLOWED_EXTRACTED_FIELDS = {"open_ports", "service_version"}
SCRIPT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")

_PORT_SPEC_RE = re.compile(r"^\d{1,5}(-\d{1,5})?(,\d{1,5}(-\d{1,5})?)*$")


def validate_target_scope(target_scope: list[str], *, require_target: bool = True) -> str | None:
    """Each entry must be a valid IPv4/IPv6 host, CIDR network, or address range.

    When `require_target` is False, an empty `target_scope` is valid (the
    profile is "target-less", FR-003a) — but a non-empty one is still fully
    validated.
    """
    if not target_scope:
        return (
            "target_scope must include at least one host, range, or subnet."
            if require_target
            else None
        )

    for entry in target_scope:
        if _is_valid_target_entry(entry):
            continue
        return f"'{entry}' is not a valid host, CIDR subnet, or address range."
    return None


def _is_valid_target_entry(entry: str) -> bool:
    entry = entry.strip()
    if not entry:
        return False
    # CIDR network, e.g. 10.0.0.0/24
    if "/" in entry:
        try:
            ipaddress.ip_network(entry, strict=False)
            return True
        except ValueError:
            return False
    # Address range, e.g. 10.0.0.1-10.0.0.50
    if "-" in entry:
        start, _, end = entry.partition("-")
        try:
            ipaddress.ip_address(start.strip())
            # Allow a bare last-octet form too, e.g. 10.0.0.1-50
            if end.strip().isdigit() and "." not in end:
                return True
            ipaddress.ip_address(end.strip())
            return True
        except ValueError:
            return False
    # Single host: IP address or hostname.
    try:
        ipaddress.ip_address(entry)
        return True
    except ValueError:
        pass
    return bool(re.match(r"^[a-zA-Z0-9]([a-zA-Z0-9\-.]{0,253})?[a-zA-Z0-9]$", entry))


def validate_port_spec(port_spec: str) -> str | None:
    """nmap-style port spec: '5060-5062', '22,80,443', '1-1024'."""
    if not port_spec or not _PORT_SPEC_RE.match(port_spec.strip()):
        return "port_spec must be a comma-separated list of ports/ranges, e.g. '5060-5062'."
    return None


def validate_scan_params(scan_params: dict) -> str | None:
    """Reject any key outside the allow-list and validate each known key's value."""
    unknown = set(scan_params) - ALLOWED_SCAN_PARAM_KEYS
    if unknown:
        return f"disallowed scan parameter(s): {', '.join(sorted(unknown))}"

    timing = scan_params.get("timing")
    if timing is not None and timing not in ALLOWED_TIMING_TEMPLATES:
        return f"timing must be one of {sorted(ALLOWED_TIMING_TEMPLATES)}"

    intensity = scan_params.get("service_version_intensity")
    if intensity is not None and not (isinstance(intensity, int) and 0 <= intensity <= 9):
        return "service_version_intensity must be an integer between 0 and 9"

    max_rate = scan_params.get("max_rate")
    if max_rate is not None and not (isinstance(max_rate, int) and max_rate > 0):
        return "max_rate must be a positive integer"

    host_timeout = scan_params.get("host_timeout_seconds")
    if host_timeout is not None and not (isinstance(host_timeout, int) and host_timeout > 0):
        return "host_timeout_seconds must be a positive integer"

    for bool_key in ("skip_host_discovery",):
        value = scan_params.get(bool_key)
        if value is not None and not isinstance(value, bool):
            return f"{bool_key} must be a boolean"

    return None


def validate_extracted_fields(extracted_fields: list[str]) -> str | None:
    """Any subset of ALLOWED_EXTRACTED_FIELDS, including empty, is valid
    (FR-005, FR-006) — only unknown field names are rejected."""
    selected = set(extracted_fields or [])
    unknown = selected - ALLOWED_EXTRACTED_FIELDS
    if unknown:
        return f"unknown extracted field(s): {', '.join(sorted(unknown))}"
    return None


def validate_selected_scripts(selected_scripts: list[str], allowlisted_ids: set[str]) -> str | None:
    """Every selected NSE script id must be a currently enabled allow-list
    entry (FR-013) — profiles never carry a free-form script name."""
    for script_id in selected_scripts or []:
        if script_id not in allowlisted_ids:
            return f"'{script_id}' is not an enabled NSE script on the allow-list."
    return None


def validate_profile(
    payload: dict,
    *,
    allowlisted_script_ids: set[str] | None = None,
    require_target: bool = True,
) -> dict[str, str]:
    """Validate a full profile payload. Returns {field: message} (empty = valid).

    `allowlisted_script_ids` should be the current set of enabled
    `NseScriptAllowlistEntry.script_id` values; when omitted, `selected_scripts`
    is not checked against the allow-list (callers that don't have a
    session handy, e.g. pure unit tests, may omit it).

    `require_target=False` allows a profile to be saved without a target
    (FR-003a); a non-empty target is still fully validated either way.
    """
    errors: dict[str, str] = {}

    if not payload.get("name"):
        errors["name"] = "name is required."

    target_error = validate_target_scope(
        payload.get("target_scope") or [], require_target=require_target
    )
    if target_error:
        errors["target_scope"] = target_error

    port_error = validate_port_spec(payload.get("port_spec", ""))
    if port_error:
        errors["port_spec"] = port_error

    scan_params_error = validate_scan_params(payload.get("scan_params") or {})
    if scan_params_error:
        errors["scan_params"] = scan_params_error

    fields_error = validate_extracted_fields(payload.get("extracted_fields") or [])
    if fields_error:
        errors["extracted_fields"] = fields_error

    if allowlisted_script_ids is not None:
        scripts_error = validate_selected_scripts(
            payload.get("selected_scripts") or [], allowlisted_script_ids
        )
        if scripts_error:
            errors["selected_scripts"] = scripts_error

    return errors

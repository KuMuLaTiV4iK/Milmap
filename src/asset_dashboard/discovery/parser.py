"""Parse nmap XML output (`-oX -`) into structured per-host results.

Uses the stdlib `xml.etree.ElementTree` (research.md's documented
fallback) rather than a third-party nmap wrapper, keeping the parsing
dependency surface minimal and the logic directly testable against
canned XML fixtures (no nmap binary required for tests).
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field


@dataclass
class ParsedPort:
    port: int
    protocol: str
    state: str
    service: str | None = None
    version: str | None = None


@dataclass
class ParsedHost:
    address: str
    up: bool
    ports: list[ParsedPort] = field(default_factory=list)
    script_output: dict[str, str] = field(default_factory=dict)  # script_id -> output text


def parse_nmap_xml(xml_text: str) -> list[ParsedHost]:
    """Parse nmap's XML report into a list of ParsedHost.

    An empty/no-host scan produces an empty list — callers distinguish
    "no responding hosts" (empty list) from a failed run (exception
    raised elsewhere, e.g. nmap missing) per FR-020.
    """
    if not xml_text.strip():
        return []

    root = ET.fromstring(xml_text)
    hosts: list[ParsedHost] = []

    for host_el in root.findall("host"):
        status_el = host_el.find("status")
        up = status_el is not None and status_el.get("state") == "up"

        address_el = host_el.find("address")
        address = address_el.get("addr") if address_el is not None else "unknown"

        ports: list[ParsedPort] = []
        script_output: dict[str, str] = {}
        ports_el = host_el.find("ports")
        if ports_el is not None:
            for port_el in ports_el.findall("port"):
                state_el = port_el.find("state")
                service_el = port_el.find("service")
                ports.append(
                    ParsedPort(
                        port=int(port_el.get("portid")),
                        protocol=port_el.get("protocol", "tcp"),
                        state=state_el.get("state") if state_el is not None else "unknown",
                        service=service_el.get("name") if service_el is not None else None,
                        version=_format_version(service_el) if service_el is not None else None,
                    )
                )
                for script_el in port_el.findall("script"):
                    script_id = script_el.get("id")
                    if script_id:
                        script_output[script_id] = script_el.get("output", "")

        hostscript_el = host_el.find("hostscript")
        if hostscript_el is not None:
            for script_el in hostscript_el.findall("script"):
                script_id = script_el.get("id")
                if script_id:
                    script_output[script_id] = script_el.get("output", "")

        hosts.append(ParsedHost(address=address, up=up, ports=ports, script_output=script_output))

    return hosts


def _format_version(service_el: ET.Element) -> str | None:
    product = service_el.get("product")
    version = service_el.get("version")
    if product and version:
        return f"{product} {version}"
    return product or version

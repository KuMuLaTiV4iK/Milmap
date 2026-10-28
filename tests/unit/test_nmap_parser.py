"""Unit tests for discovery/parser.py (nmap XML -> structured results)."""

from asset_dashboard.discovery.parser import parse_nmap_xml

SAMPLE_XML = """<?xml version="1.0"?>
<nmaprun>
  <host>
    <status state="up"/>
    <address addr="10.10.0.5" addrtype="ipv4"/>
    <ports>
      <port protocol="udp" portid="5060">
        <state state="open"/>
        <service name="sip" product="Asterisk PBX" version="16.2.1"/>
      </port>
    </ports>
  </host>
  <host>
    <status state="down"/>
    <address addr="10.10.0.6" addrtype="ipv4"/>
    <ports/>
  </host>
</nmaprun>
"""


def test_parses_open_port_and_service_version():
    hosts = parse_nmap_xml(SAMPLE_XML)
    assert len(hosts) == 2

    up_host = next(h for h in hosts if h.address == "10.10.0.5")
    assert up_host.up is True
    assert len(up_host.ports) == 1
    port = up_host.ports[0]
    assert port.port == 5060
    assert port.protocol == "udp"
    assert port.service == "sip"
    assert port.version == "Asterisk PBX 16.2.1"


def test_down_host_has_no_ports():
    hosts = parse_nmap_xml(SAMPLE_XML)
    down_host = next(h for h in hosts if h.address == "10.10.0.6")
    assert down_host.up is False
    assert down_host.ports == []


def test_empty_output_yields_empty_list():
    # Distinguishes "no responding hosts" (empty list) from a failed run,
    # which is raised as an exception elsewhere (FR-020).
    assert parse_nmap_xml("") == []


def test_no_host_elements_yields_empty_list():
    assert parse_nmap_xml("<?xml version='1.0'?><nmaprun></nmaprun>") == []

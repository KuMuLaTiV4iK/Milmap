"""Unit tests for discovery/nmap_runner.py command construction (FR-001,
FR-005-FR-010, FR-015).

Only allow-listed scan_params/extracted_fields/selected_scripts ever reach
the command line — there is no path here that accepts a raw flag string.
"""
from asset_dashboard.discovery.nmap_runner import build_nmap_command


def test_builds_basic_command_with_ports_and_targets():
    cmd = build_nmap_command(["10.10.0.0/24"], "5060-5062", {})
    assert cmd[0] == "nmap"
    assert "-oX" in cmd and "-" in cmd
    assert "-p" in cmd and "5060-5062" in cmd
    assert "10.10.0.0/24" in cmd


def test_timing_defaults_to_t3_when_unspecified():
    cmd = build_nmap_command(["10.0.0.1"], "22", {})
    assert "-T3" in cmd


def test_timing_template_maps_to_dash_t_flag():
    cmd = build_nmap_command(["10.0.0.1"], "22", {"timing": "T4"})
    assert "-T4" in cmd
    assert "-T3" not in cmd


def test_sv_flag_included_iff_service_version_extracted():
    cmd = build_nmap_command(["10.0.0.1"], "22", {}, extracted_fields=["service_version"])
    assert "-sV" in cmd

    cmd_without = build_nmap_command(["10.0.0.1"], "22", {}, extracted_fields=["open_ports"])
    assert "-sV" not in cmd_without

    cmd_empty = build_nmap_command(["10.0.0.1"], "22", {}, extracted_fields=[])
    assert "-sV" not in cmd_empty


def test_max_rate_and_host_timeout_translate_correctly():
    cmd = build_nmap_command(["10.0.0.1"], "22", {"max_rate": 100, "host_timeout_seconds": 30})
    assert "--max-rate" in cmd
    assert "100" in cmd
    assert "--host-timeout" in cmd
    assert "30s" in cmd


def test_skip_host_discovery_maps_to_pn_flag():
    cmd = build_nmap_command(["10.0.0.1"], "22", {"skip_host_discovery": True})
    assert "-Pn" in cmd


def test_no_raw_flags_accepted_in_command_construction():
    # build_nmap_command only ever reads known keys; an unknown key (which
    # validate_scan_params would already have rejected upstream) is simply
    # ignored here, never interpolated into the command line.
    cmd = build_nmap_command(["10.0.0.1"], "22", {"raw_flags": "-sS --script vuln"})
    assert "vuln" not in cmd


def test_selected_scripts_emit_single_script_flag():
    cmd = build_nmap_command(
        ["10.0.0.1"], "8291", {}, selected_scripts=["mikrotik-routeros-version"]
    )
    assert "--script" in cmd
    idx = cmd.index("--script")
    assert cmd[idx + 1] == "mikrotik-routeros-version"


def test_multiple_selected_scripts_are_comma_joined():
    cmd = build_nmap_command(["10.0.0.1"], "22", {}, selected_scripts=["banner", "other-script"])
    idx = cmd.index("--script")
    assert cmd[idx + 1] == "banner,other-script"


def test_no_selected_scripts_means_no_script_flag():
    cmd = build_nmap_command(["10.0.0.1"], "22", {}, selected_scripts=[])
    assert "--script" not in cmd

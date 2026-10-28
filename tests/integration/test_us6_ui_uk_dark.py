"""Integration/smoke test for User Story 6: dark SOC interface in
Ukrainian with inline help (see spec.md US6 Independent Test): every
screen renders dark + Ukrainian + Milmap; a `?` help affordance appears on
config controls; T3/-sV/ports/script ids remain literal English."""

PROFILE = {
    "name": "UI smoke profile",
    "description": "",
    "target_scope": ["10.0.0.1"],
    "port_spec": "22",
    "scan_params": {"timing": "T3"},
    "extracted_fields": ["open_ports"],
    "compliance_settings": {},
    "cache_freshness_seconds": 3600,
}

PAGES = [
    "/",
    "/profiles",
    "/profiles/new",
    "/history",
    "/schedules",
    "/tools/credential-check",
    "/configuration",
]


def test_every_page_renders_milmap_brand_and_dark_theme(authed_client):
    for path in PAGES:
        resp = authed_client.get(path)
        assert resp.status_code == 200, path
        assert "Milmap" in resp.text, path
        assert "base.css" in resp.text, path


def test_every_page_has_ukrainian_nav_labels(authed_client):
    resp = authed_client.get("/")
    assert "Профілі" in resp.text
    assert "Конфігурація" in resp.text
    assert "Вийти" in resp.text


def test_login_page_is_ukrainian(client):
    resp = client.get("/login")
    assert "Вхід" in resp.text
    assert "Milmap" in resp.text


def test_configuration_controls_carry_help_affordance(admin_client):
    page = admin_client.get("/configuration")
    assert "help-icon" in page.text


def test_profile_editor_help_affordance_and_english_technical_ids(authed_client):
    page = authed_client.get("/profiles/new")
    assert "help-icon" in page.text
    # Technical identifiers stay literal English.
    assert 'value="T3"' in page.text
    assert 'value="T4"' in page.text


def test_run_detail_shows_dark_theme_and_english_ports(authed_client, monkeypatch):
    from asset_dashboard.discovery import nmap_runner

    sample_xml = """<?xml version="1.0"?>
<nmaprun><host><status state="up"/><address addr="10.0.0.1" addrtype="ipv4"/>
<ports><port protocol="tcp" portid="22"><state state="open"/></port></ports>
</host></nmaprun>"""

    class _FakeProcess:
        def __init__(self, stdout):
            self.stdout = stdout
            self.returncode = 0

        def communicate(self):
            return self.stdout, ""

        def poll(self):
            return self.returncode

        def terminate(self):
            pass

    def fake_start_nmap(
        target_scope, port_spec, scan_params, extracted_fields=None, selected_scripts=None
    ):
        return nmap_runner.NmapRunHandle(process=_FakeProcess(sample_xml), command=["nmap"])

    monkeypatch.setattr(nmap_runner, "start_nmap", fake_start_nmap)

    import time

    profile = authed_client.post("/api/profiles", json=PROFILE).json()
    start = authed_client.post(f"/api/profiles/{profile['id']}/runs", json={})
    run_id = start.json()["run_id"]

    deadline = time.time() + 3
    while time.time() < deadline:
        run = authed_client.get(f"/api/runs/{run_id}").json()
        if run["status"] != "running":
            break
        time.sleep(0.02)

    page = authed_client.get(f"/runs/{run_id}")
    assert page.status_code == 200
    assert "22/tcp" in page.text  # literal English technical identifier
    assert "Milmap" in page.text

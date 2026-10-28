"""FR-038: every configuration control id referenced by a template must
have a Ukrainian help entry in web/i18n.py's HELP registry."""

import re
from pathlib import Path

from asset_dashboard.web.i18n import HELP, help_for, t

TEMPLATES_DIR = (
    Path(__file__).resolve().parents[2] / "src" / "asset_dashboard" / "web" / "templates"
)

_HELP_ICON_CALL_RE = re.compile(r"help_icon\('([a-z0-9_]+)'\)")


def _referenced_control_ids() -> set[str]:
    ids: set[str] = set()
    for template_path in TEMPLATES_DIR.glob("*.html"):
        text = template_path.read_text(encoding="utf-8")
        ids.update(_HELP_ICON_CALL_RE.findall(text))
    return ids


def test_every_template_referenced_control_id_has_help_text():
    referenced = _referenced_control_ids()
    assert referenced, "expected at least one help_icon() call across templates"
    missing = referenced - set(HELP)
    assert not missing, f"missing Ukrainian help text for control ids: {missing}"


def test_help_for_known_control_returns_non_empty_text():
    assert help_for("password_min_length") != ""
    assert help_for("timing") != ""


def test_help_for_unknown_control_is_empty_not_an_error():
    assert help_for("not-a-real-control-id") == ""


def test_t_falls_back_to_key_for_unknown_translation():
    assert t("this.key.does.not.exist") == "this.key.does.not.exist"


def test_t_returns_ukrainian_for_known_key():
    assert t("app.brand") == "Milmap"

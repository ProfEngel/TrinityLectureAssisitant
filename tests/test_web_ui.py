from web_ui import render_web_ui


def test_web_settings_group_harness_frameworks_together():
    html = render_web_ui()

    assert "Agenten-Frameworks" in html
    assert "Rollen je Framework (JSON)" in html
    assert "Agenten-Ausfuehrung je Framework (JSON)" in html
    assert "addHarnessTestButtons" in html
    assert "'/harness/test'" in html
    assert "title:'Codex'" not in html
    assert "title:'OpenCode'" not in html
    assert "title:'Pi'" not in html

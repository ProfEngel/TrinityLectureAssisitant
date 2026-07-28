from web_ui import render_web_ui


def test_web_settings_group_harness_frameworks_together():
    html = render_web_ui()

    assert "Agenten-Frameworks" in html
    assert "Rollen je Framework inkl. Trinity (JSON)" in html
    assert "Agenten-Ausfuehrung je Framework (JSON)" in html
    assert "Agentenkatalog: Reifegrad, Rechte, Freigaben, Limits (JSON)" in html
    assert "addHarnessTestButtons" in html
    assert "'/harness/test'" in html
    assert "['trinity','Trinity']" in html
    assert "title:'Codex'" not in html
    assert "title:'OpenCode'" not in html
    assert "title:'Pi'" not in html
    assert "Goose" not in html


def test_web_ui_contains_workbench_profile_badge_and_thesis_pilot():
    html = render_web_ui()

    assert 'data-view="workbench"' in html
    assert 'id="profileBadge"' in html
    assert "Trinity-Werkstatt" in html
    assert "Abschlussarbeit begutachten" in html
    assert "'/workbench/catalog'" in html
    assert "'/workbench/run'" in html
    assert "#werkstatt" in html
    assert 'id="presentationPanel"' in html
    assert 'id="presentationScaffoldPanel"' in html
    assert 'id="presentationPlanEditor"' in html
    assert 'id="jobCenterToggle"' in html
    assert "'/workbench/jobs?limit=40'" in html
    assert "'/workbench/presentation/approve'" in html
    assert "'/workbench/secrets'" in html
    assert 'src="/trinity-logo"' in html
    assert "Codex / ChatGPT oder OpenCode" in html
    assert "updateHarnessFields" in html
    assert "job-meter" in html
    assert "Aktuell: Schritt" in html
    assert "Eingaben dürfen dabei leer bleiben" in html
    assert "Kie.ai API-Schlüssel" in html
    assert "gpt-image-2-text-to-image" not in html
    assert "fal.ai API-Schlüssel · Fallback" not in html

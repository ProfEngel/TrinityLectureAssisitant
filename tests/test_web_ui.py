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
    assert "Vorhandene Präsentation modernisieren" in html
    assert "html-presentation-modernize" in html
    assert "presentationMode:'new'" in html
    assert "genau eine Ausgangspräsentation als PPTX oder PDF" in html
    assert 'id="jobCenterToggle"' in html
    assert "'/workbench/jobs?limit=40'" in html
    assert "'/workbench/presentation/approve'" in html
    assert "'/workbench/job/cancel'" in html
    assert "'/workbench/job/delete'" in html
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
    assert "get('embedded')==='1'" in html


def test_web_header_uses_accessible_symbol_controls():
    html = render_web_ui()

    assert 'class="header-actions" aria-label="Trinity-Steuerung"' in html
    assert 'id="newSession" title="Neue Session" aria-label="Neue Session"' in html
    assert 'id="jobCenterToggle" title="Agentenstatus"' in html
    assert 'id="jobCount"' in html
    assert 'id="runtimeModeControl" title="Modus: Vorlesung"' in html
    assert 'id="microphoneToggle" title="Mikrofon"' in html
    assert 'id="ttsToggle" title="Lautsprecher"' in html
    assert 'id="settingsView" title="Einstellungen"' in html
    assert 'id="saveToken" title="Zugang: Zugriffstoken"' in html
    assert 'class="toolbar-icon"' in html
    assert "microphoneToggle.textContent" not in html
    assert "ttsToggle.textContent" not in html


def test_authenticated_web_header_uses_symbolic_access_control():
    html = render_web_ui(auth_enabled=True)

    assert 'id="login" title="Zugang: Anmelden"' in html
    assert "Zugang: Administrator anlegen" in html

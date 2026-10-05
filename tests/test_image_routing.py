import types
import pytest
from core.brain import TrinityBrain
from core.image_routing import is_image_request, image_skill_allowed


@pytest.mark.parametrize("query", [
    "Erstelle ein Schaubild zu RAG", "Trinity, mach uns ein Diagramm",
    "Ich hätte gerne eine Infografik", "Zeige mir ein Bild von einer Metapher",
    "Erstelle ein Diagramm aus diesen CSV-Daten", "Erstelle ein Bild zum Thema Musik",
    "Kannst du mir ein Schaubild zu RAG?", "Trinity, ein Diagramm dazu bitte",
])
def test_creation_is_raster(query):
    assert is_image_request(query)
    assert image_skill_allowed(types.SimpleNamespace(__name__="agents.comfyui_agent"), query)
    assert not image_skill_allowed(types.SimpleNamespace(__name__="agents.sandbox_agent"), query)


@pytest.mark.parametrize("query", ["Was siehst du auf diesem Bild?", "Erkläre dieses Diagramm", "Was macht das Bild so gut?", "Was zeigt dieses Bild?", "Was ist ein Diagramm?"])
def test_image_analysis_is_not_creation(query):
    assert not is_image_request(query)


def test_external_requires_explicit_request():
    skill = types.SimpleNamespace(__name__="agents.image_agent")
    assert not image_skill_allowed(skill, "Erstelle ein Diagramm")
    assert image_skill_allowed(skill, "Erstelle ein externes Diagramm")


@pytest.mark.parametrize("mode", ["success", "failure", "missing", "exception"])
def test_image_dispatch_never_falls_back_to_mermaid(tmp_path, monkeypatch, mode):
    brain = TrinityBrain.__new__(TrinityBrain)
    brain.api_key = ""
    brain._soul_cache = brain._user_cache = ""
    calls = []
    def execute(query, context=None):
        calls.append("image")
        if mode == "exception":
            raise RuntimeError("offline")
        return {"has_payload": mode == "success", "html_payload": '<img src="image.png">',
                "search_context": "ComfyUI ist nicht erreichbar." if mode == "failure" else ""}
    brain.live_skills = [types.SimpleNamespace(__name__="agents.sandbox_agent", can_handle=lambda q: True,
        execute=lambda *a, **kw: pytest.fail("Mermaid/code tools must never be called"))]
    if mode != "missing":
        brain.live_skills.append(types.SimpleNamespace(__name__="agents.comfyui_agent", can_handle=lambda q: False, execute=execute))
    brain.unavailable_skills = []
    monkeypatch.setattr("core.brain.diagnostic", lambda *a: None)
    monkeypatch.setattr("core.brain.requests.post", lambda *a, **kw: pytest.fail("No LLM fallback"))
    transcript = tmp_path / "transcript.md"
    transcript.write_text("")
    answer, payload = brain.ask("Erstelle ein Diagramm zum Thema Musik", str(transcript))
    assert payload == (mode == "success")
    assert "mermaid" not in answer.lower()
    assert ("fertig" in answer) == (mode == "success")
    assert len(calls) == (0 if mode == "missing" else 1)


def test_media_status_always_finishes_on_error(tmp_path, monkeypatch):
    brain = TrinityBrain.__new__(TrinityBrain)
    brain.config_path = str(tmp_path / "core/config.json")
    events = []
    monkeypatch.setattr("core.brain.diagnostic", lambda home, stage, message: events.append(message))
    def fail(query, context=None):
        raise RuntimeError("offline")
    with pytest.raises(RuntimeError):
        brain._execute_media_skill(fail, "Erstelle ein Bild", {})
    assert events == ["started", "finished"]

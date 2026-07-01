from core.brain import TrinityBrain
import json
import types


class _DirectAnswerSkill:
    PRIORITY = 100

    @staticmethod
    def can_handle(_query):
        return True

    @staticmethod
    def execute(_query, context=None):
        return {
            "has_payload": False,
            "html_payload": "",
            "search_context": "",
            "direct_answer": "Direktes Codex-Ergebnis",
        }


def test_brain_returns_skill_direct_answer_without_llm(tmp_path, monkeypatch):
    brain = TrinityBrain.__new__(TrinityBrain)
    brain.api_key = ""
    brain.url = "http://unused"
    brain.model = "unused"
    brain.live_skills = [_DirectAnswerSkill]
    brain.unavailable_skills = []
    brain._telegram_cfg = {}
    brain._codex_cfg = {}
    brain._soul_cache = ""
    brain._user_cache = ""

    def fail_request(*_args, **_kwargs):
        raise AssertionError("Das LLM darf bei direct_answer nicht aufgerufen werden.")

    monkeypatch.setattr("core.brain.requests.post", fail_request)
    transcript = tmp_path / "transcript.md"
    transcript.write_text("", encoding="utf-8")

    answer, has_payload = brain.ask(
        "Trinity, Codex erledige die Aufgabe",
        str(transcript),
    )

    assert answer == "Direktes Codex-Ergebnis"
    assert has_payload is False


def test_brain_dispatches_skill_via_context_handler_without_llm(tmp_path, monkeypatch):
    class ContextSkill:
        PRIORITY = 100

        @staticmethod
        def can_handle(_query):
            return False

        @staticmethod
        def can_handle_with_context(query, context=None):
            return "eldoria" in query and bool((context or {}).get("pi_cfg", {}).get("enabled"))

        @staticmethod
        def execute(_query, context=None):
            return {
                "has_payload": False,
                "html_payload": "",
                "search_context": "",
                "direct_answer": "Kontextskill hat Eldoria an Pi delegiert.",
            }

    brain = TrinityBrain.__new__(TrinityBrain)
    brain.api_key = ""
    brain.url = "http://unused"
    brain.model = "unused"
    brain.live_skills = [ContextSkill]
    brain.unavailable_skills = []
    brain._telegram_cfg = {}
    brain._codex_cfg = {}
    brain._opencode_cfg = {}
    brain._pi_cfg = {"enabled": True}
    brain._soul_cache = ""
    brain._user_cache = ""

    def fail_request(*_args, **_kwargs):
        raise AssertionError("Das LLM darf bei contextbasiertem Skill-Routing nicht aufgerufen werden.")

    monkeypatch.setattr("core.brain.requests.post", fail_request)
    transcript = tmp_path / "transcript.md"
    transcript.write_text("", encoding="utf-8")

    answer, has_payload = brain.ask(
        "Trinity, welches Kapitel ist aktuell in Eldoria?",
        str(transcript),
    )

    assert answer == "Kontextskill hat Eldoria an Pi delegiert."
    assert has_payload is False


def test_brain_sends_image_attachment_as_multimodal_content(tmp_path, monkeypatch):
    brain = TrinityBrain.__new__(TrinityBrain)
    brain.api_key = "key"
    brain.url = "http://llm"
    brain.model = "vision-model"
    brain.live_skills = []
    brain.unavailable_skills = []
    brain._telegram_cfg = {}
    brain._codex_cfg = {}
    brain._soul_cache = ""
    brain._user_cache = ""
    brain.last_media_path = None
    captured = {}

    class Response:
        status_code = 200

        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return {"choices": [{"message": {"content": "Bild erkannt"}}]}

    def fake_request(_url, headers, json, timeout):
        captured["data"] = json
        return Response()

    monkeypatch.setattr("core.brain.requests.post", fake_request)
    transcript = tmp_path / "transcript.md"
    transcript.write_text("", encoding="utf-8")
    image = tmp_path / "slide.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nimage")

    answer, _ = brain.ask(
        "Was zeigt die Folie?",
        str(transcript),
        attachments=[
            {
                "name": "slide.png",
                "path": str(image),
                "kind": "image",
                "mime": "image/png",
            }
        ],
    )

    user_content = captured["data"]["messages"][-1]["content"]
    assert answer == "Bild erkannt"
    assert user_content[1]["type"] == "image_url"
    assert brain.last_media_path == str(image)


def test_image_attachment_skips_generation_skill_for_vision_question(tmp_path, monkeypatch):
    brain = TrinityBrain.__new__(TrinityBrain)
    brain.api_key = "key"
    brain.url = "http://llm"
    brain.model = "vision-model"
    brain.live_skills = [
        types.SimpleNamespace(
            __name__="agents.image_agent",
            can_handle=lambda _query: True,
            execute=lambda _query, context=None: {
                "has_payload": False,
                "html_payload": "",
                "search_context": "",
                "direct_answer": "Falsch abgebogen",
            },
        )
    ]
    brain.unavailable_skills = []
    brain._telegram_cfg = {}
    brain._codex_cfg = {}
    brain._soul_cache = ""
    brain._user_cache = ""
    brain.last_media_path = None

    class Response:
        status_code = 200

        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return {"choices": [{"message": {"content": "Vision-Antwort"}}]}

    monkeypatch.setattr("core.brain.requests.post", lambda *_args, **_kwargs: Response())
    transcript = tmp_path / "transcript.md"
    transcript.write_text("", encoding="utf-8")
    image = tmp_path / "chart.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nimage")

    answer, _ = brain.ask(
        "Was siehst du auf dem angehängten Bild?",
        str(transcript),
        attachments=[{"name": "chart.png", "path": str(image), "kind": "image"}],
    )

    assert answer == "Vision-Antwort"


def test_explicit_local_image_edit_may_use_comfyui_skill(tmp_path, monkeypatch):
    brain = TrinityBrain.__new__(TrinityBrain)
    brain.api_key = "key"
    brain.url = "http://llm"
    brain.model = "vision-model"
    brain.live_skills = [
        types.SimpleNamespace(
            __name__="agents.comfyui_agent",
            can_handle=lambda _query: True,
            execute=lambda _query, context=None: {
                "has_payload": True,
                "html_payload": "<p>ok</p>",
                "search_context": "",
                "direct_answer": "ComfyUI gestartet",
            },
        )
    ]
    brain.unavailable_skills = []
    brain._telegram_cfg = {}
    brain._codex_cfg = {}
    brain._soul_cache = ""
    brain._user_cache = ""
    brain.last_media_path = None

    def fail_request(*_args, **_kwargs):
        raise AssertionError("Explizite lokale Bildbearbeitung soll zum Skill routen.")

    monkeypatch.setattr("core.brain.requests.post", fail_request)
    transcript = tmp_path / "transcript.md"
    transcript.write_text("", encoding="utf-8")
    image = tmp_path / "chart.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nimage")

    answer, has_payload = brain.ask(
        "Nimm dieses Bild und ändere es lokal mit ComfyUI.",
        str(transcript),
        attachments=[{"name": "chart.png", "path": str(image), "kind": "image"}],
    )

    assert answer == "ComfyUI gestartet"
    assert has_payload is True


def test_brain_reload_runtime_config_updates_model_without_restart(tmp_path):
    config_path = tmp_path / "config.json"
    soul_path = tmp_path / "Soul.md"
    user_path = tmp_path / "User.md"
    soul_path.write_text("Soul eins", encoding="utf-8")
    user_path.write_text("User eins", encoding="utf-8")
    config_path.write_text(
        json.dumps(
            {
                "llm": {
                    "active_slot": "local",
                    "local": {
                        "url": "http://one",
                        "model": "model-one",
                        "api_key": "key-one",
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    brain = TrinityBrain.__new__(TrinityBrain)
    brain.config_path = str(config_path)
    brain.soul_path = str(soul_path)
    brain.user_path = str(user_path)
    brain._runtime_signature = {}
    brain.load_config()
    brain._soul_cache = brain.get_file_content(brain.soul_path)
    brain._user_cache = brain.get_file_content(brain.user_path)
    brain._remember_runtime_signature()

    config_path.write_text(
        json.dumps(
            {
                "llm": {
                    "active_slot": "local",
                    "local": {
                        "url": "http://two",
                        "model": "model-two",
                        "api_key": "key-two",
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    soul_path.write_text("Soul zwei", encoding="utf-8")

    assert brain.reload_runtime_config(force=True) is True
    assert brain.url == "http://two"
    assert brain.model == "model-two"
    assert brain.api_key == "key-two"
    assert brain.get_soul() == "Soul zwei"

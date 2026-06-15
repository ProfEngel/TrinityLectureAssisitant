from core.brain import TrinityBrain


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

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

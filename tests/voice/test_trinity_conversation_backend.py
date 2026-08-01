import json

from voice.conversation.trinity_backend import TrinityConversationBackend


class FakeBrain:
    def __init__(self):
        self.queries = []

    def ask(self, query, *_args, **_kwargs):
        self.queries.append(query)
        return "Verstanden.", False


def backend_for(tmp_path, mode):
    core = tmp_path / "core"
    core.mkdir()
    (core / "config.json").write_text(
        json.dumps({
            "system": {"mode": mode},
            "persona": {"trigger_variants": ["trinity", "triniti"]},
        }),
        encoding="utf-8",
    )
    backend = TrinityConversationBackend(tmp_path)
    backend._brain = FakeBrain()
    backend._append_chat_events = lambda *_args, **_kwargs: None
    return backend


def test_lecture_voice_ignores_speech_without_wakeword(tmp_path):
    backend = backend_for(tmp_path, "lecture")

    assert list(backend.respond("Heute geht es um Spieltheorie")) == []
    assert backend._brain.queries == []


def test_lecture_voice_answers_after_fuzzy_wakeword(tmp_path):
    backend = backend_for(tmp_path, "lecture")

    assert list(backend.respond("Triniti, erkläre das Nash-Gleichgewicht")) == ["Verstanden."]
    assert backend._brain.queries == ["Triniti, erkläre das Nash-Gleichgewicht"]


def test_office_voice_answers_without_wakeword(tmp_path):
    backend = backend_for(tmp_path, "office")

    assert list(backend.respond("Erkläre das Nash-Gleichgewicht")) == ["Verstanden."]
    assert backend._brain.queries == ["Erkläre das Nash-Gleichgewicht"]


def test_legacy_chat_mode_behaves_like_office(tmp_path):
    backend = backend_for(tmp_path, "chat")

    assert list(backend.respond("Erkläre das Nash-Gleichgewicht")) == ["Verstanden."]

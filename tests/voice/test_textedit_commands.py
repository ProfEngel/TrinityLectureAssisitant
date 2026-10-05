import json

from voice.conversation.trinity_backend import TrinityConversationBackend
from voice.textedit_commands import HELP_TEXT, command_for, revision_instruction, notes_topic


def test_observed_summary_requests_with_trailing_address_and_selection():
    for text in ["Fasse das Diktat zusammen, Trinity.",
                 "Fasse das Diktat zusammen, ich habe es markiert. Trinity",
                 "Fasse das Diktat zusammen, ich habe es markiert.",
                 "Trinity, bitte fasse den markierten Text zusammen."]:
        assert command_for(text) == "summarize"
    assert command_for("Fasse das Diktat zusammen, Trinity", dictating=True) == "summarize"
    assert command_for("Fasse das Diktat zusammen", dictating=True) is None
    assert command_for("Wir wollten das Diktat zusammenfassen Trinity") is None


def test_parameterized_edits_are_explicit_and_do_not_execute_app_actions():
    text = "Trinity, ändere den Satz über Modelle in Spiegelpunkte."
    assert command_for(text) == "revise"
    assert revision_instruction(text) == "ändere den Satz über Modelle in Spiegelpunkte."
    assert command_for(text, dictating=True) == "revise"
    assert command_for("Ändere den Satz über Modelle in Spiegelpunkte", dictating=True) is None
    assert revision_instruction("Trinity, sende die Mail") == ""


def test_internal_compaction_never_calls_brain_or_persists_history(tmp_path, monkeypatch):
    backend = TrinityConversationBackend(tmp_path)
    monkeypatch.setattr(backend, "_ensure_brain", lambda: (_ for _ in ()).throw(AssertionError("brain called")))
    text = "Summarize the following conversation.  Return only the JSON object.\n--- CONVERSATION START ---\nUser: Gestern"
    assert list(backend.respond(text)) == []
    assert "Gestern" not in backend.transcript_path.read_text()


def test_topic_notes_are_explicit_and_scoped_to_a_topic():
    text = "Trinity, schreibe unsere Gedanken zum Thema Transformer."
    assert command_for(text) == "write_notes"
    assert notes_topic(text) == "Transformer."
    assert command_for(text, dictating=True) == "write_notes"
    assert command_for("Wir sollten unsere Gedanken zum Thema Transformer schreiben") is None


def test_dictation_control_supersedes_an_inflight_old_answer(tmp_path, monkeypatch):
    import threading
    (tmp_path / "core").mkdir()
    (tmp_path / "core/config.json").write_text(json.dumps({"system": {
        "mode": "office", "audio_input": {"kind": "desktop", "device_id": "desktop:mac"},
        "textedit_voice_device_id": "desktop:mac",
    }}))
    backend = TrinityConversationBackend(tmp_path)
    entered, finish = threading.Event(), threading.Event()
    class Brain:
        def ask(self, *args, **kwargs):
            entered.set()
            assert finish.wait(3)
            return "Veraltete Antwort", False
    monkeypatch.setattr(backend, "_ensure_brain", lambda: Brain())
    saved = []
    monkeypatch.setattr(backend, "_append_chat_events", lambda *args: saved.append(args))
    result = []
    worker = threading.Thread(target=lambda: result.extend(backend.respond("Eine frühere Frage")))
    worker.start()
    assert entered.wait(2)
    assert list(backend.respond("Diktat starten")) == []
    finish.set()
    worker.join(3)
    assert not worker.is_alive()
    assert result == [] and saved == []
from voice.textedit_lease import TextEditVoiceLease


def test_commands_require_whole_utterances_and_allow_explicit_wakeword_free_start_stop():
    assert command_for("Trinity, ich diktiere jetzt.") == "dictation_start"
    assert command_for("Trinity, Diktat starten") == "dictation_start"
    assert command_for("Drinitä, ich diktiere jetzt.") == "dictation_start"
    assert command_for("Tinity, Diktat starten.") == "dictation_start"
    assert command_for("Drinitä, Diktat beenden.", dictating=True) == "dictation_stop"
    assert command_for("Trinity, Diktat Ben.") == "dictation_invalid"
    assert command_for("Trinity, aktives Fenster erfassen") == "window_capture_on"
    assert command_for("Trinity, Fenstererfassung ausschalten", dictating=True) == "window_capture_off"
    assert command_for("Wir sollten das aktive Fenster erfassen", dictating=True) is None
    assert command_for("Einfügen.") == "insert_last"
    assert command_for("Trinity, was kannst du hier beim Schreiben tun?") == "help"
    assert command_for("Trinity, zeig mir die Schreibbefehle.") == "show_help"
    assert command_for("Trinity, Bearbeitung abschließen.") == "close_draft"
    assert command_for("Trinity, schreibe die Schreibbefehle hier hinein.") == "help_insert"
    assert command_for("Kannst du das zusammenfassen?") == "summarize"
    assert command_for("Lass uns das besser überarbeiten.") == "revise"
    assert command_for("Ja, das klingt viel besser.") == "accept_revision"
    assert command_for("Trinity, Diktat beenden.", dictating=True) == "dictation_stop"
    assert command_for("Diktat beenden.", dictating=True) == "dictation_stop"
    assert command_for("Diktat Ende.", dictating=True) == "dictation_stop"
    assert command_for("Diktat starten.") == "dictation_start"
    assert command_for("Drinete ich, ich diktiere jetzt.") == "dictation_start"
    assert command_for("Heute reden wir über Diktat starten", dictating=True) is None
    assert command_for("Fasse das Diktat zusammen") == "summarize"
    assert command_for("Formuliere das besser") == "revise"
    assert command_for("Übernimm die neue Fassung") == "accept_revision"
    assert command_for("Ich möchte das Wort einfügen verwenden.") is None
    assert command_for("Trinity, lösche alle Dateien") is None
    assert "Diktat beenden" in HELP_TEXT


def test_desktop_dictation_never_calls_brain_or_saves_prose(tmp_path, monkeypatch):
    core = tmp_path / "core"
    core.mkdir()
    (core / "config.json").write_text(json.dumps({
        "system": {
            "audio_input": {"kind": "desktop", "device_id": "desktop:privat:mac"},
            "textedit_voice_device_id": "desktop:privat:mac",
        },
    }))
    backend = TrinityConversationBackend(tmp_path)
    monkeypatch.setattr(backend, "_ensure_brain", lambda: (_ for _ in ()).throw(AssertionError("brain called")))
    assert list(backend.respond("Trinity, ich diktiere jetzt")) == []
    assert list(backend.respond("Drinitä, ich diktiere jetzt")) == []
    assert list(backend.respond("Trinity Diktat Ben")) == []
    assert list(backend.respond("Diktat starten")) == []
    assert list(backend.respond("Unbekannt, ich diktiere jetzt")) == ["Startbefehl nicht sicher erkannt. Sag bitte nur: Diktat starten."]
    TextEditVoiceLease(tmp_path / "TrinityRuntime/voice/textedit_lease.json").update(
        "desktop:privat:mac", True, None)
    assert list(backend.respond("Das ist mein Fließtext.")) == []
    assert list(backend.respond("Trinity, Diktat beenden")) == []
    assert list(backend.respond("Trinity, was kannst du hier beim Schreiben tun?"))
    assert "Fließtext" not in backend.transcript_path.read_text()


def test_failed_mac_dictation_start_does_not_silence_conversation(tmp_path, monkeypatch):
    core = tmp_path / "core"
    core.mkdir()
    (core / "config.json").write_text(json.dumps({"system": {
        "mode": "office", "audio_input": {"kind": "desktop", "device_id": "desktop:mac"},
        "textedit_voice_device_id": "desktop:mac",
    }}))
    backend = TrinityConversationBackend(tmp_path)
    class Brain:
        def ask(self, *args, **kwargs):
            return "Ja, ich höre dich.", False
    monkeypatch.setattr(backend, "_ensure_brain", lambda: Brain())
    monkeypatch.setattr(backend, "_append_chat_events", lambda *args: None)
    assert list(backend.respond("Trinity, ich diktiere jetzt")) == []
    # The Mac could not focus TextEdit, so it never confirms an editor lease.
    assert list(backend.respond("Trinity, kannst du mich hören?")) == ["Ja, ich höre dich."]
    assert command_for("Trinity stopp", dictating=True) == "dictation_stop"
    assert command_for("Das ist mein Text. Trinity Diktat beendet", dictating=True) == "dictation_stop"


def test_companion_voice_does_not_activate_textedit_commands(tmp_path, monkeypatch):
    core = tmp_path / "core"
    core.mkdir()
    (core / "config.json").write_text(json.dumps({
        "system": {"audio_input": {"kind": "companion", "device_id": "ipad"}},
    }))
    backend = TrinityConversationBackend(tmp_path)
    assert not backend._desktop_microphone_selected()


def test_other_desktop_does_not_activate_mac_textedit_commands(tmp_path):
    core = tmp_path / "core"
    core.mkdir()
    (core / "config.json").write_text(json.dumps({
        "system": {
            "audio_input": {"kind": "desktop", "device_id": "desktop:biz:windows"},
            "textedit_voice_device_id": "desktop:privat:mac",
        },
    }))
    assert not TrinityConversationBackend(tmp_path)._desktop_microphone_selected()

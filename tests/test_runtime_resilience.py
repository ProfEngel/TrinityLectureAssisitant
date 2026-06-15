import json
from pathlib import Path

import trinity_launcher
from core import transcriber


def test_windows_config_disables_speech_input_by_default(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "stt": {
                    "model": "small",
                    "silence_threshold": 0.015,
                    "chunk_duration": 2,
                },
                "tts": {"voice": "Standard"},
                "system": {"mode": "office"},
            }
        ),
        encoding="utf-8",
    )

    ear = object.__new__(transcriber.MorpheusEar)
    ear.config_path = str(config_path)
    monkeypatch.setattr(transcriber.sys, "platform", "win32")

    ear.load_config()

    assert ear.mode == "office"
    assert ear.speech_input_enabled is False


def test_windows_speech_can_be_enabled_explicitly(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "stt": {
                    "model": "small",
                    "silence_threshold": 0.015,
                    "chunk_duration": 2,
                },
                "tts": {"voice": "Standard"},
                "system": {
                    "mode": "office",
                    "windows_speech_enabled": True,
                },
            }
        ),
        encoding="utf-8",
    )

    ear = object.__new__(transcriber.MorpheusEar)
    ear.config_path = str(config_path)
    monkeypatch.setattr(transcriber.sys, "platform", "win32")

    ear.load_config()

    assert ear.speech_input_enabled is True


def test_runtime_failure_creates_visible_diagnostic(tmp_path):
    core_dir = tmp_path / "core"
    core_dir.mkdir()

    trinity_launcher._show_runtime_error(str(tmp_path), -1073741819)

    payload = (core_dir / "payload.html").read_text(encoding="utf-8")
    state = (core_dir / "state.txt").read_text(encoding="utf-8")
    assert "Trinity-Kern wurde beendet" in payload
    assert "-1073741819" in payload
    assert state == "reporting"


def test_show_terminal_defaults_to_false_for_invalid_config(tmp_path):
    config_path = Path(tmp_path) / "config.json"
    config_path.write_text("{invalid", encoding="utf-8")

    assert trinity_launcher._read_show_terminal(str(config_path)) is False


def test_whisper_command_works_without_loading_audio(tmp_path, monkeypatch):
    core_dir = tmp_path / "core"
    memory_dir = tmp_path / "memory"
    core_dir.mkdir()
    memory_dir.mkdir()
    (core_dir / "cmd.txt").write_text(
        "SILENT:Teste die LLM-Verbindung",
        encoding="utf-8",
    )
    received = []

    class FakeBrain:
        pass

    class FakeTTS:
        pass

    def fake_load_config(ear):
        ear.model_name = "small"
        ear.silence_threshold = 0.015
        ear.chunk_duration = 2
        ear.show_volume_meter = False
        ear.voice = "Standard"
        ear.agent_name = "Trinity"
        ear.trigger_variants = ["trinity"]
        ear.proactive_cfg = {}
        ear.audio_routing = {}
        ear.telegram_cfg = {}
        ear.system_cfg = {
            "mode": "office",
            "windows_speech_enabled": False,
        }
        ear.mode = "office"
        ear.speech_input_enabled = False

    def fake_trigger(ear, text, silent_response=False, **_kwargs):
        received.append((text, silent_response))
        ear.is_running = False

    monkeypatch.setattr(transcriber, "__file__", str(core_dir / "transcriber.py"))
    monkeypatch.setattr(transcriber, "MEMORY_DIR", str(memory_dir))
    monkeypatch.setattr(transcriber, "TrinityBrain", FakeBrain)
    monkeypatch.setattr(transcriber, "create_tts_backend", lambda: FakeTTS())
    monkeypatch.setattr(transcriber.MorpheusEar, "load_config", fake_load_config)
    monkeypatch.setattr(transcriber.MorpheusEar, "trigger_action", fake_trigger)

    ear = transcriber.MorpheusEar()
    ear.start()

    assert received == [("Teste die LLM-Verbindung", True)]
    assert ear._whisper is None
    assert ear.audio_stream is None

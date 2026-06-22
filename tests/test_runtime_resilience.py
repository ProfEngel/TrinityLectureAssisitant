import json
import sys
import time
import types
from pathlib import Path

import trinity_launcher

if "requests" not in sys.modules:
    try:
        import requests  # noqa: F401
    except ModuleNotFoundError:
        sys.modules["requests"] = types.ModuleType("requests")

from core import transcriber
from chat_protocol import build_chat_request, encode_chat_request
from external_stt_feed import append_external_stt_event


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

    ear = object.__new__(transcriber.TrinityEar)
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

    ear = object.__new__(transcriber.TrinityEar)
    ear.config_path = str(config_path)
    monkeypatch.setattr(transcriber.sys, "platform", "win32")

    ear.load_config()

    assert ear.speech_input_enabled is True


def test_runtime_reload_applies_saved_settings(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "stt": {
                    "model": "small",
                    "silence_threshold": 0.015,
                    "chunk_duration": 2,
                },
                "tts": {"voice": "Old Voice"},
                "system": {"mode": "office"},
                "telegram": {"enabled": False, "bot_token": "", "chat_id": ""},
            }
        ),
        encoding="utf-8",
    )

    ear = object.__new__(transcriber.TrinityEar)
    ear.config_path = str(config_path)
    ear.brain = type(
        "Brain",
        (),
        {"reload_runtime_config": lambda self, force=False: True},
    )()
    monkeypatch.setattr(transcriber.sys, "platform", "darwin")
    ear.audio_stream = None
    ear.load_config()

    config_path.write_text(
        json.dumps(
            {
                "stt": {
                    "model": "small",
                    "silence_threshold": 0.015,
                    "chunk_duration": 2,
                },
                "tts": {"voice": "New Voice"},
                "system": {"mode": "chat"},
                "telegram": {
                    "enabled": True,
                    "bot_token": "token",
                    "chat_id": "123",
                },
            }
        ),
        encoding="utf-8",
    )
    ear._config_mtime = 0

    assert ear.reload_config_if_changed() is True
    assert ear.voice == "New Voice"
    assert ear.mode == "chat"
    assert ear.telegram_cfg["enabled"] is True


def test_love_questions_do_not_trigger_affection_mode():
    assert (
        transcriber.is_affection_directed_at_trinity(
            "Erkläre mir was Liebe ist?",
            "Trinity",
        )
        is False
    )
    assert (
        transcriber.is_affection_directed_at_trinity(
            "Und was ist Liebe für Lebende?",
            "Trinity",
        )
        is False
    )
    assert (
        transcriber.is_affection_directed_at_trinity(
            "Trinity, ich liebe dich",
            "Trinity",
        )
        is True
    )


def test_runtime_failure_creates_visible_diagnostic(tmp_path):
    core_dir = tmp_path / "core"
    core_dir.mkdir()
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    runtime_log = logs_dir / "runtime.log"
    runtime_log.write_text("Traceback\nImportError: demo\n", encoding="utf-8")

    trinity_launcher._show_runtime_error(
        str(tmp_path),
        -1073741819,
        str(runtime_log),
    )

    payload = (core_dir / "payload.html").read_text(encoding="utf-8")
    state = (core_dir / "state.txt").read_text(encoding="utf-8")
    assert "Trinity-Kern wurde beendet" in payload
    assert "-1073741819" in payload
    assert "ImportError: demo" in payload
    assert state == "reporting"


def test_invalid_config_keeps_a_graphical_ui_available(tmp_path):
    config_path = Path(tmp_path) / "config.json"
    config_path.write_text("{invalid", encoding="utf-8")

    modes = trinity_launcher._read_ui_modes(str(config_path))

    assert modes["classic"] is True
    assert modes["eyes"] is False


def test_launcher_reads_companion_bridge_config(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "companion": {
                    "enabled": True,
                    "host": "0.0.0.0",
                    "port": 8765,
                    "token": "secret",
                }
            }
        ),
        encoding="utf-8",
    )

    companion = trinity_launcher._read_companion_config(str(config_path))

    assert companion["enabled"] is True
    assert companion["host"] == "0.0.0.0"
    assert companion["token"] == "secret"


def test_windows_terminal_uses_console_python_from_pythonw(tmp_path):
    pythonw = tmp_path / "pythonw.exe"
    python = tmp_path / "python.exe"
    pythonw.touch()
    python.touch()

    resolved = trinity_launcher._console_python_executable(
        str(pythonw),
        platform_name="win32",
    )

    assert resolved == str(python)


def test_launcher_forces_utf8_for_child_processes():
    env = trinity_launcher._trinity_subprocess_env({"PATH": "demo"})

    assert env["PATH"] == "demo"
    assert env["PYTHONIOENCODING"] == "utf-8"
    assert env["PYTHONUTF8"] == "1"


def test_surface_argument_is_read_for_cli_start():
    assert (
        trinity_launcher._requested_surface(
            ["trinity_launcher.py", "--surface", "classic"]
        )
        == "classic"
    )


def test_linux_headless_detection_uses_display_environment():
    assert (
        trinity_launcher._graphical_session_available(
            platform_name="linux",
            environment={},
        )
        is False
    )
    assert (
        trinity_launcher._graphical_session_available(
            platform_name="linux",
            environment={"DISPLAY": ":0"},
        )
        is True
    )


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
    monkeypatch.setattr(transcriber, "CORE_DIR", str(core_dir))
    monkeypatch.setattr(transcriber, "MEMORY_DIR", str(memory_dir))
    monkeypatch.setattr(transcriber, "TrinityBrain", FakeBrain)
    monkeypatch.setattr(transcriber, "create_tts_backend", lambda: FakeTTS())
    monkeypatch.setattr(transcriber.TrinityEar, "load_config", fake_load_config)
    monkeypatch.setattr(transcriber.TrinityEar, "trigger_action", fake_trigger)

    ear = transcriber.TrinityEar()
    ear.start()

    assert received == [("Teste die LLM-Verbindung", True)]
    assert ear._whisper is None
    assert ear.audio_stream is None


def test_structured_classic_command_reaches_runtime_with_attachments(
    tmp_path,
    monkeypatch,
):
    core_dir = tmp_path / "core"
    memory_dir = tmp_path / "memory"
    core_dir.mkdir()
    memory_dir.mkdir()
    request = build_chat_request(
        "Analysiere das Bild",
        [{"name": "bild.png", "path": "/tmp/bild.png", "kind": "image"}],
        history_recorded=True,
    )
    (core_dir / "cmd.txt").write_text(
        encode_chat_request(request),
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
        ear.system_cfg = {"mode": "chat"}
        ear.mode = "chat"
        ear.speech_input_enabled = False

    def fake_trigger(ear, text, silent_response=False, **kwargs):
        received.append((text, silent_response, kwargs["chat_request"]))
        ear.is_running = False

    monkeypatch.setattr(transcriber, "__file__", str(core_dir / "transcriber.py"))
    monkeypatch.setattr(transcriber, "MEMORY_DIR", str(memory_dir))
    monkeypatch.setattr(transcriber, "CHAT_HISTORY_FILE", str(memory_dir / "chat.jsonl"))
    monkeypatch.setattr(transcriber, "TrinityBrain", FakeBrain)
    monkeypatch.setattr(transcriber, "create_tts_backend", lambda: FakeTTS())
    monkeypatch.setattr(transcriber.TrinityEar, "load_config", fake_load_config)
    monkeypatch.setattr(transcriber.TrinityEar, "trigger_action", fake_trigger)

    ear = transcriber.TrinityEar()
    ear.start()

    assert received[0][0] == "Analysiere das Bild"
    assert received[0][1] is True
    assert received[0][2]["attachments"][0]["name"] == "bild.png"


def test_ios_stt_trigger_word_works_in_chat_mode(tmp_path, monkeypatch):
    core_dir = tmp_path / "core"
    memory_dir = tmp_path / "memory"
    core_dir.mkdir()
    memory_dir.mkdir()
    append_external_stt_event(
        core_dir / "ios_stt_feed.jsonl",
        {
            "source": "ios-stt",
            "text": "Trinity erklär mir Spieltheorie",
            "is_final": False,
            "speak": False,
        },
    )
    append_external_stt_event(
        core_dir / "ios_stt_feed.jsonl",
        {
            "source": "ios-stt",
            "text": "Trinity erklär mir Spieltheorie",
            "is_final": True,
            "speak": False,
        },
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
        ear.system_cfg = {"mode": "chat"}
        ear.mode = "chat"
        ear.speech_input_enabled = False

    def fake_trigger(ear, text, silent_response=False, recent_text=None, **kwargs):
        received.append((text, silent_response, recent_text, kwargs.get("chat_request")))
        ear.is_running = False

    monkeypatch.setattr(transcriber, "__file__", str(core_dir / "transcriber.py"))
    monkeypatch.setattr(transcriber, "CORE_DIR", str(core_dir))
    monkeypatch.setattr(transcriber, "MEMORY_DIR", str(memory_dir))
    monkeypatch.setattr(transcriber, "TrinityBrain", FakeBrain)
    monkeypatch.setattr(transcriber, "create_tts_backend", lambda: FakeTTS())
    monkeypatch.setattr(transcriber.TrinityEar, "load_config", fake_load_config)
    monkeypatch.setattr(transcriber.TrinityEar, "trigger_action", fake_trigger)

    ear = transcriber.TrinityEar()
    ear.start()

    assert received
    assert "Trinity erklär mir Spieltheorie" in received[0][0]
    assert received[0][1] is True
    assert received[0][3]["source"] == "ios-stt"


def test_ios_stt_trigger_word_creates_bridge_request_in_lecture_mode(tmp_path, monkeypatch):
    core_dir = tmp_path / "core"
    memory_dir = tmp_path / "memory"
    core_dir.mkdir()
    memory_dir.mkdir()
    append_external_stt_event(
        core_dir / "ios_stt_feed.jsonl",
        {
            "source": "ios-stt",
            "text": "Trinity erklär mir Spieltheorie",
            "is_final": True,
            "speak": False,
            "session_id": "ios-session",
            "privacy_mode": "local",
        },
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
        ear.system_cfg = {"mode": "lecture"}
        ear.mode = "lecture"
        ear.speech_input_enabled = False

    def fake_trigger(ear, text, silent_response=False, recent_text=None, **kwargs):
        received.append((text, silent_response, recent_text, kwargs.get("chat_request")))
        ear.is_running = False

    monkeypatch.setattr(transcriber, "__file__", str(core_dir / "transcriber.py"))
    monkeypatch.setattr(transcriber, "CORE_DIR", str(core_dir))
    monkeypatch.setattr(transcriber, "MEMORY_DIR", str(memory_dir))
    monkeypatch.setattr(transcriber, "TrinityBrain", FakeBrain)
    monkeypatch.setattr(transcriber, "create_tts_backend", lambda: FakeTTS())
    monkeypatch.setattr(transcriber.TrinityEar, "load_config", fake_load_config)
    monkeypatch.setattr(transcriber.TrinityEar, "trigger_action", fake_trigger)

    ear = transcriber.TrinityEar()
    ear.start()

    assert received
    assert "Trinity erklär mir Spieltheorie" in received[0][0]
    assert received[0][1] is True
    assert received[0][3]["source"] == "ios-stt"
    assert received[0][3]["session_id"] == "ios-session"


def test_ios_stt_echo_of_recent_assistant_response_is_ignored(tmp_path, monkeypatch):
    core_dir = tmp_path / "core"
    memory_dir = tmp_path / "memory"
    core_dir.mkdir()
    memory_dir.mkdir()
    assistant_answer = (
        "Ich habe die Folien durchgesehen und die technischen Begriffe in "
        "betriebswirtschaftliche Vergleiche übersetzt. Soll ich die "
        "Zusammenfassung direkt für das Plenum aufbereiten?"
    )
    append_external_stt_event(
        core_dir / "ios_stt_feed.jsonl",
        {
            "source": "ios-stt",
            "text": (
                "Ich habe die Folien durchgesehen und die technischen Begriffe "
                "in betriebswirtschaftliche Vergleiche übersetzt soll ich die "
                "Zusammenfassung direkt für das Plenum"
            ),
            "is_final": True,
            "speak": False,
        },
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
        ear.system_cfg = {"mode": "chat"}
        ear.mode = "chat"
        ear.speech_input_enabled = False

    def fake_trigger(ear, text, silent_response=False, **kwargs):
        received.append((text, silent_response, kwargs.get("chat_request")))

    monkeypatch.setattr(transcriber, "__file__", str(core_dir / "transcriber.py"))
    monkeypatch.setattr(transcriber, "CORE_DIR", str(core_dir))
    monkeypatch.setattr(transcriber, "MEMORY_DIR", str(memory_dir))
    monkeypatch.setattr(transcriber, "TrinityBrain", FakeBrain)
    monkeypatch.setattr(transcriber, "create_tts_backend", lambda: FakeTTS())
    monkeypatch.setattr(transcriber.TrinityEar, "load_config", fake_load_config)
    monkeypatch.setattr(transcriber.TrinityEar, "trigger_action", fake_trigger)

    ear = transcriber.TrinityEar()
    ear._last_assistant_response = assistant_answer
    ear._last_assistant_response_at = time.time()
    ear._process_external_stt_feed()

    assert received == []

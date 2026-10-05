from pathlib import Path

import voice.runtime as runtime_module
from voice.config import default_voice_config, load_voice_config
from voice.runtime import VoiceRuntime


def ubuntu_config(tmp_path):
    reference = tmp_path / "Eve.mp3"
    reference.write_bytes(b"voice")
    voice = default_voice_config()
    voice.update({
        "engine": "eve",
        "profile": "eve-linux-gpu-server",
        "access_token": "voice-secret",
        "reference_audio": str(reference),
        "remote_core_base_url": "http://windows.tailnet:18767/v1",
        "remote_core_api_key": "core-secret",
    })
    return load_voice_config(tmp_path, {"voice": voice})


def test_ubuntu_runtime_starts_and_stops_dedicated_stt_service(tmp_path, monkeypatch):
    events = []

    class FakeProcess:
        returncode = 0

        def poll(self):
            return None

        def terminate(self):
            events.append("process-terminate")

        def wait(self, timeout=None):
            events.append(("process-wait", timeout))
            return 0

    class FakeProxy:
        def __init__(self, *args):
            events.append(("proxy-init", args))

        def start(self):
            events.append("proxy-start")

        def stop(self):
            events.append("proxy-stop")

    class FakeTranscriber:
        def __init__(self, model_name, device):
            events.append(("stt-transcriber", model_name, device))

    class FakeSTTServer:
        def __init__(self, host, port, token, transcriber):
            events.append(("stt-init", host, port, token, type(transcriber).__name__))

        def start(self):
            events.append("stt-start")

        def stop(self):
            events.append("stt-stop")

    monkeypatch.setattr(runtime_module, "build_speech_to_speech_command", lambda _config: ["voice"])
    monkeypatch.setattr(runtime_module.subprocess, "Popen", lambda *_args, **_kwargs: FakeProcess())
    monkeypatch.setattr(runtime_module, "_wait_for_port", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(runtime_module, "AuthenticatedWebSocketProxy", FakeProxy)
    monkeypatch.setattr(runtime_module, "CudaParakeetTranscriber", FakeTranscriber)
    monkeypatch.setattr(runtime_module, "ParakeetSTTHTTPServer", FakeSTTServer)

    runtime = VoiceRuntime(ubuntu_config(tmp_path))
    runtime.start()

    assert "proxy-start" in events
    assert (
        "stt-init",
        "0.0.0.0",
        8767,
        "voice-secret",
        "FakeTranscriber",
    ) in events
    assert "stt-start" in events

    runtime.stop()

    assert events.index("stt-stop") < events.index("proxy-stop")
    assert "process-terminate" in events


def test_mac_client_never_starts_local_conversation_backend(tmp_path, monkeypatch):
    events = []
    voice = default_voice_config()
    voice.update({
        "engine": "eve",
        "profile": "trinity-mac-client",
        "remote_voice_url": "ws://linux.tailnet:8766/v1/realtime",
        "remote_voice_token": "voice-secret",
    })
    config = load_voice_config(tmp_path, {"voice": voice})

    class FakeAudioClient:
        def __init__(self, _config, endpoint, access_token):
            events.append(("audio", endpoint, access_token))

        def start(self):
            events.append("started")

    monkeypatch.setattr(runtime_module, "LocalRealtimeAudioClient", FakeAudioClient)
    monkeypatch.setattr(runtime_module, "TrinityConversationBackend", lambda *_: events.append("brain"))
    monkeypatch.setattr(runtime_module.subprocess, "Popen", lambda *_a, **_k: events.append("inference"))
    runtime = VoiceRuntime(config)
    runtime.start()
    assert events == [("audio", "ws://linux.tailnet:8766/v1/realtime", "voice-secret"), "started"]

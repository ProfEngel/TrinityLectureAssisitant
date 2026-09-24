import json
import threading

from core.voice.config import default_voice_config, load_voice_config
from core.voice.local_realtime_client import LocalRealtimeAudioClient


def test_remote_connection_uri_adds_token_and_preserves_query(tmp_path):
    raw = default_voice_config()
    raw.update(
        {
            "profile": "eve-windows-remote",
            "access_token": "voice secret",
            "remote_voice_url": "wss://voice.example.test/v1/realtime?client=windows",
            "backend_token": "core-secret",
        }
    )
    config = load_voice_config(tmp_path, {"voice": raw})
    client = LocalRealtimeAudioClient(
        config,
        endpoint=config.remote_voice_url,
        access_token=config.access_token,
    )

    assert client._connection_uri() == (
        "wss://voice.example.test/v1/realtime?client=windows&access_token=voice+secret"
    )


def test_remote_client_stays_alive_while_ubuntu_is_unavailable(tmp_path, monkeypatch):
    raw = default_voice_config()
    raw.update(
        {
            "profile": "eve-windows-remote",
            "access_token": "voice-secret",
            "remote_voice_url": "ws://ubuntu.invalid:8766/v1/realtime",
            "backend_token": "core-secret",
        }
    )
    config = load_voice_config(tmp_path, {"voice": raw})
    client = LocalRealtimeAudioClient(config, endpoint=config.remote_voice_url)
    client._mic_claim_path.parent.mkdir(parents=True)
    client._mic_claim_path.write_text("stale", encoding="utf-8")
    client._legacy_released_path.write_text("stale", encoding="utf-8")
    attempted = threading.Event()

    def unavailable():
        attempted.set()
        raise ConnectionError("host is still booting")

    monkeypatch.setattr(client, "_run_connection", unavailable)
    client.start(timeout=1)
    assert attempted.wait(1)
    assert client.is_alive
    assert client.failure is None
    assert not client._mic_claim_path.exists()
    assert not client._legacy_released_path.exists()

    client.stop()
    assert not client.is_alive


def test_reconnect_discards_audio_from_previous_connection(tmp_path):
    raw = default_voice_config()
    raw.update(
        {
            "profile": "eve-windows-remote",
            "access_token": "voice-secret",
            "remote_voice_url": "ws://ubuntu.invalid:8766/v1/realtime",
            "backend_token": "core-secret",
        }
    )
    config = load_voice_config(tmp_path, {"voice": raw})
    client = LocalRealtimeAudioClient(config, endpoint=config.remote_voice_url)
    client._queue_event({"type": "input_audio_buffer.append", "audio": "stale"})

    client._discard_pending_input()

    assert client._send_queue.empty()


def test_remote_client_only_claims_pipeline_for_desktop_speaker(tmp_path, monkeypatch):
    raw = default_voice_config()
    raw.update(
        {
            "profile": "eve-windows-remote",
            "access_token": "voice-secret",
            "remote_voice_url": "ws://ubuntu.invalid:8766/v1/realtime",
            "backend_token": "core-secret",
        }
    )
    config = load_voice_config(tmp_path, {"voice": raw})
    config_path = tmp_path / "core" / "config.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        json.dumps({"system": {"speech_output": {"kind": "companion"}}}),
        encoding="utf-8",
    )
    client = LocalRealtimeAudioClient(config, endpoint=config.remote_voice_url)
    attempted = threading.Event()

    def connect_once():
        attempted.set()
        client._stop.set()

    monkeypatch.setattr(client, "_run_connection", connect_once)
    client.start(timeout=1)

    assert not attempted.wait(0.7)

    config_path.write_text(
        json.dumps({"system": {"speech_output": {"kind": "desktop"}}}),
        encoding="utf-8",
    )

    assert attempted.wait(1.5)
    client.stop()

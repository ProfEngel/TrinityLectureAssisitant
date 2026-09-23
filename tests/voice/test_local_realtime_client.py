from core.voice.config import default_voice_config, load_voice_config
from core.voice.local_realtime_client import LocalRealtimeAudioClient
import core.voice.local_realtime_client as client_module
import json
import platform


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


def test_remote_mac_audio_only_plays_for_selected_mac(tmp_path, monkeypatch):
    (tmp_path / "core").mkdir()
    (tmp_path / "core" / "config.json").write_text(json.dumps({
        "client": {"enabled": True, "server_url": "http://linux.tailnet:8765", "token": "bridge-secret"},
        "system": {"profile": "PRIVAT"},
    }))
    raw = default_voice_config()
    raw.update({"profile": "trinity-mac-client", "remote_voice_url": "ws://linux.tailnet:8766/v1/realtime", "remote_voice_token": "voice-secret"})
    client = LocalRealtimeAudioClient(load_voice_config(tmp_path, {"voice": raw}))
    assert not client._desktop_speaker_selected()
    assert "device_id=desktop%3Aprivat%3A" in client._connection_uri()

    class Response:
        def __enter__(self):
            client._stop.set()
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({
                "ok": True,
                "device_id": f"desktop:privat:{platform.node().strip() or 'Desktop'}",
            }).encode()

    monkeypatch.setattr(client_module, "urlopen", lambda *_args, **_kwargs: Response())
    client._poll_remote_speaker()
    assert client._desktop_speaker_selected()

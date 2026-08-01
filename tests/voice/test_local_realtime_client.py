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

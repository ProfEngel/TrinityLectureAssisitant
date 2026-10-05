from core.voice.config import default_voice_config, load_voice_config
from core.voice.local_realtime_client import LocalRealtimeAudioClient
import core.voice.local_realtime_client as client_module
import json
import platform
import threading


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
                "device_id": client._remote_speaker_id,
            }).encode()

    monkeypatch.setattr(client_module, "urlopen", lambda *_args, **_kwargs: Response())
    client._poll_remote_speaker()
    assert client._desktop_speaker_selected()


def test_send_failure_reconnects_without_stopping_desktop_client(tmp_path):
    raw = default_voice_config()
    raw.update({"profile": "trinity-mac-client", "remote_voice_url": "ws://linux.tailnet:8766/v1/realtime"})
    client = LocalRealtimeAudioClient(load_voice_config(tmp_path, {"voice": raw}))
    session_stop = threading.Event()

    class BrokenSocket:
        def __init__(self):
            self.closed = False

        def send(self, _payload):
            raise ConnectionError("server restarting")

        def close(self):
            self.closed = True

    socket = BrokenSocket()
    client._queue_event({"type": "input_audio_buffer.append", "audio": "AA=="})
    client._send_loop(socket, session_stop)
    assert session_stop.is_set()
    assert socket.closed
    assert not client._stop.is_set()


def test_echo_check_survives_concurrent_output_buffer_change(tmp_path, monkeypatch):
    import time
    import numpy as np
    client = LocalRealtimeAudioClient(load_voice_config(tmp_path, {"voice": default_voice_config()}))
    client._last_output_at = time.monotonic()
    samples = np.full(512, 12000, dtype=np.int16)
    client._played_output.append(samples.astype(np.float32))
    original_norm = np.linalg.norm
    def changing_norm(value, *args, **kwargs):
        # Simulate the output callback running while the input callback is
        # calculating its correlation. This crashed iteration of the deque.
        with client._echo_lock:
            client._played_output.append(samples.astype(np.float32))
        return original_norm(value, *args, **kwargs)
    monkeypatch.setattr(np.linalg, "norm", changing_norm)
    assert isinstance(client._should_forward_microphone(samples.tobytes()), bool)

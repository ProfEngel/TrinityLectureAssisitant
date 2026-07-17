import base64
import json
import threading
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen

import numpy as np
import pytest

from bridge_audio import BridgeAudioTranscriber, G2_SAMPLE_RATE
from trinity_bridge import TrinityBridge, make_handler


def test_bridge_audio_decodes_signed_16_bit_pcm():
    samples = np.array([-32768, -1000, 0, 1000, 32767], dtype="<i2")
    encoded = base64.b64encode(samples.tobytes()).decode("ascii")

    decoded = BridgeAudioTranscriber.decode_pcm(encoded, sample_rate=G2_SAMPLE_RATE)

    assert decoded.dtype == np.float32
    assert decoded[0] == -1.0
    assert decoded[-1] == pytest.approx(32767 / 32768)


def test_bridge_audio_rejects_wrong_sample_rate_and_oversized_audio():
    encoded = base64.b64encode(b"\x00\x00").decode("ascii")
    with pytest.raises(ValueError, match="16-kHz"):
        BridgeAudioTranscriber.decode_pcm(encoded, sample_rate=48_000)

    oversized = base64.b64encode(b"\x00\x00" * (G2_SAMPLE_RATE * 20 + 1)).decode("ascii")
    with pytest.raises(ValueError, match="hoechstens"):
        BridgeAudioTranscriber.decode_pcm(oversized)


def test_audio_transcription_http_endpoint_accepts_authenticated_g2_request(tmp_path):
    (tmp_path / "core").mkdir()
    (tmp_path / "memory").mkdir()
    bridge = TrinityBridge(tmp_path, token="secret")

    class FakeTranscriber:
        def transcribe(self, _audio_base64, **_kwargs):
            return {"text": "Trinity Test", "language": "de"}

    bridge._audio_transcriber = FakeTranscriber()
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(bridge))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = Request(
            f"http://127.0.0.1:{server.server_port}/audio/transcribe",
            data=json.dumps({"audio_base64": "cGNt", "route": "none"}).encode("utf-8"),
            headers={"Authorization": "Bearer secret", "Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=3) as response:
            payload = json.load(response)
        assert payload["ok"] is True
        assert payload["text"] == "Trinity Test"
        assert payload["routed"] is False
    finally:
        server.shutdown()
        server.server_close()

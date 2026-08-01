import base64
import json
import threading
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen

import numpy as np
import pytest

from bridge_audio import (
    BridgeAudioTranscriber,
    G2_SAMPLE_RATE,
    TRINITY_HOTWORDS,
    TRINITY_VOCABULARY,
)
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


def test_bridge_audio_biases_short_g2_commands_without_reusing_previous_text():
    calls = []

    class Segment:
        text = " Trinity, Modus Zuruf "

    class Info:
        language = "de"
        language_probability = 0.99

    class FakeModel:
        def transcribe(self, _audio, **kwargs):
            calls.append(kwargs)
            return [Segment()], Info()

    transcriber = BridgeAudioTranscriber()
    transcriber._model = FakeModel()
    encoded = base64.b64encode(np.full(1600, 1200, dtype="<i2").tobytes()).decode("ascii")

    result = transcriber.transcribe(encoded)

    assert result["text"] == "Trinity, Modus Zuruf"
    assert calls[0]["condition_on_previous_text"] is False
    assert calls[0]["beam_size"] == 2
    assert calls[0]["hotwords"] == "Trinity"
    assert "Schnellsession" not in calls[0]["initial_prompt"]
    assert calls[0]["best_of"] == 1

    transcriber.transcribe(encoded, quality="precise")
    assert calls[1]["beam_size"] == 4

    with pytest.raises(ValueError, match="Erkennungsqualitaet"):
        transcriber.transcribe(encoded, quality="maximum")


def test_bridge_audio_prompt_does_not_bias_spontaneous_checklist_hallucinations():
    prompt = f"{TRINITY_VOCABULARY} {TRINITY_HOTWORDS}".lower()

    assert "checkliste" not in prompt
    assert "wichtige begriffe" not in prompt
    assert "stichwoerter" not in prompt


@pytest.mark.parametrize(
    "text",
    [
        "Copyright WDR 2024",
        "Untertitel im Auftrag des ZDF",
        "Untertitel der Amara.org Community",
        "www.schnellsessions.com",
    ],
)
def test_bridge_audio_filters_known_subtitle_and_domain_hallucinations(text):
    assert BridgeAudioTranscriber.is_known_hallucination(text)


def test_bridge_audio_drops_silent_audio_without_loading_the_model():
    transcriber = BridgeAudioTranscriber()
    transcriber._ensure_model = lambda: (_ for _ in ()).throw(AssertionError("model must stay unloaded"))
    encoded = base64.b64encode(b"\x00\x00" * 1600).decode("ascii")

    assert transcriber.transcribe(encoded)["text"] == ""


def test_bridge_audio_drops_low_confidence_no_speech_segments():
    class Segment:
        text = " Copyright WDR "
        no_speech_prob = 0.91
        avg_logprob = -1.2

    class Info:
        language = "de"
        language_probability = 0.99

    class FakeModel:
        def transcribe(self, _audio, **_kwargs):
            return [Segment()], Info()

    transcriber = BridgeAudioTranscriber()
    transcriber._model = FakeModel()
    encoded = base64.b64encode(np.full(1600, 1200, dtype="<i2").tobytes()).decode("ascii")

    assert transcriber.transcribe(encoded)["text"] == ""


def test_audio_transcription_http_endpoint_accepts_authenticated_g2_request(tmp_path):
    (tmp_path / "core").mkdir()
    (tmp_path / "memory").mkdir()
    bridge = TrinityBridge(tmp_path, token="secret")

    class FakeTranscriber:
        def transcribe(self, _audio_base64, **kwargs):
            assert kwargs["quality"] == "precise"
            return {"text": "Trinity Test", "language": "de"}

    bridge._audio_transcriber = FakeTranscriber()
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(bridge))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = Request(
            f"http://127.0.0.1:{server.server_port}/audio/transcribe",
            data=json.dumps({"audio_base64": "cGNt", "quality": "precise", "route": "none"}).encode("utf-8"),
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

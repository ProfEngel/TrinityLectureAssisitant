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


def test_bridge_audio_uses_parakeet_without_allocating_a_conversation_pipeline():
    class Result:
        text = " Trinity, bist du da? "

    class FakeParakeet:
        def generate(self, audio):
            assert len(audio) == 1600
            return Result()

    transcriber = BridgeAudioTranscriber(backend="parakeet")
    transcriber._model = FakeParakeet()
    transcriber._transcribe_parakeet = lambda audio: transcriber._model.generate(audio)
    encoded = base64.b64encode(np.full(1600, 1200, dtype="<i2").tobytes()).decode("ascii")

    result = transcriber.transcribe(encoded)

    assert result["text"] == "Trinity, bist du da?"
    assert result["engine"] == "parakeet"
    assert result["language"] == "de"


def test_bridge_audio_uses_remote_eve_transcription_with_voice_token():
    received = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, *_args):
            return json.dumps({
                "ok": True,
                "text": "Trinity, bist du da?",
                "language": "de",
            }).encode("utf-8")

    def requester(request, timeout=None):
        received.append((request, timeout))
        return FakeResponse()

    transcriber = BridgeAudioTranscriber(
        backend="eve-remote",
        remote_voice_url="ws://ubuntu.tailnet:8766/v1/realtime",
        remote_voice_token="secret token",
        remote_requester=requester,
    )
    encoded = base64.b64encode(np.full(3200, 1200, dtype="<i2").tobytes()).decode("ascii")

    result = transcriber.transcribe(encoded)

    assert result["text"] == "Trinity, bist du da?"
    assert result["engine"] == "eve-remote"
    request, timeout = received[0]
    assert request.full_url == "http://ubuntu.tailnet:8767/v1/audio/transcriptions"
    assert request.headers["Authorization"] == "Bearer secret token"
    assert json.loads(request.data)["sample_rate"] == 16_000
    assert timeout == 12


def test_bridge_audio_explicit_remote_stt_url_overrides_derived_url():
    transcriber = BridgeAudioTranscriber(
        backend="eve-remote",
        remote_voice_url="wss://voice.example.test:8766/v1/realtime",
        remote_stt_url="https://stt.example.test/custom",
    )

    assert transcriber.remote_stt_url == "https://stt.example.test/custom"
    assert BridgeAudioTranscriber.derive_remote_stt_url(
        transcriber.remote_voice_url
    ) == "https://voice.example.test:8767/v1/audio/transcriptions"


def test_bridge_audio_remote_failure_falls_back_to_local_whisper():
    class Segment:
        text = " Lokales Fallback "
        no_speech_prob = 0.0
        avg_logprob = 0.0

    class Info:
        language = "de"
        language_probability = 0.95

    class FakeWhisper:
        def transcribe(self, _audio, **_kwargs):
            return [Segment()], Info()

    transcriber = BridgeAudioTranscriber(
        backend="eve-remote",
        remote_voice_url="ws://ubuntu.tailnet:8766/v1/realtime",
    )
    transcriber._transcribe_eve_remote = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        ConnectionError("Ubuntu nicht erreichbar")
    )
    transcriber._fallback_model = FakeWhisper()
    encoded = base64.b64encode(np.full(1600, 1200, dtype="<i2").tobytes()).decode("ascii")

    result = transcriber.transcribe(encoded)

    assert result["text"] == "Lokales Fallback"
    assert result["engine"] == "whisper-fallback"
    assert result["remote_error"] == "Ubuntu nicht erreichbar"


def test_windows_remote_voice_profile_selects_remote_companion_stt(tmp_path):
    (tmp_path / "core").mkdir()
    (tmp_path / "memory").mkdir()
    bridge = TrinityBridge(tmp_path)
    config = {
        "stt": {"companion_backend": "auto"},
        "voice": {
            "engine": "eve",
            "profile": "eve-windows-remote",
            "remote_voice_url": "ws://ubuntu.tailnet:8766/v1/realtime",
            "remote_stt_url": "http://ubuntu.tailnet:8767/v1/audio/transcriptions",
            "remote_voice_token": "secret",
        },
    }

    transcriber = bridge._make_audio_transcriber(config)

    assert transcriber.backend == "eve-remote"
    assert transcriber.remote_voice_url == "ws://ubuntu.tailnet:8766/v1/realtime"
    assert transcriber.remote_stt_url == "http://ubuntu.tailnet:8767/v1/audio/transcriptions"
    assert transcriber.remote_voice_token == "secret"


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

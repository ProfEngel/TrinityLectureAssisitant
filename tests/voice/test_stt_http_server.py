import base64
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import numpy as np
import pytest

from voice.stt_http_server import CudaParakeetTranscriber, ParakeetSTTHTTPServer


class FakeTranscriber:
    def __init__(self):
        self._model = object()

    def warm_up(self):
        return None

    def transcribe(self, audio_base64, **kwargs):
        assert audio_base64
        assert kwargs["sample_rate"] == 16_000
        return {
            "text": "Trinity Test",
            "language": "de",
            "language_probability": 1.0,
            "engine": "parakeet-cuda",
        }


def request_json(url, token="secret", data=None):
    headers = {"Authorization": f"Bearer {token}"}
    body = None
    if data is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(data).encode("utf-8")
    request = Request(url, data=body, headers=headers, method="POST" if body else "GET")
    with urlopen(request, timeout=3) as response:
        return response.status, json.load(response)


def test_authenticated_stt_endpoint_transcribes_without_realtime_slot():
    server = ParakeetSTTHTTPServer("127.0.0.1", 0, "secret", FakeTranscriber())
    server.start()
    port = server._server.server_port
    try:
        encoded = base64.b64encode(np.full(1600, 1200, dtype="<i2").tobytes()).decode()
        status, payload = request_json(
            f"http://127.0.0.1:{port}/v1/audio/transcriptions",
            data={"audio_base64": encoded, "sample_rate": 16_000},
        )
        assert status == 200
        assert payload["text"] == "Trinity Test"
        assert payload["engine"] == "parakeet-cuda"
    finally:
        server.stop()


def test_stt_endpoint_rejects_wrong_token():
    server = ParakeetSTTHTTPServer("127.0.0.1", 0, "secret", FakeTranscriber())
    server.start()
    port = server._server.server_port
    try:
        with pytest.raises(HTTPError) as error:
            request_json(f"http://127.0.0.1:{port}/health", token="wrong")
        assert error.value.code == 401
    finally:
        server.stop()


def test_cuda_parakeet_pcm_validation_happens_before_model_load():
    transcriber = CudaParakeetTranscriber("nvidia/parakeet-tdt-0.6b-v3")
    transcriber._ensure_model = lambda: (_ for _ in ()).throw(
        AssertionError("model must stay unloaded")
    )

    with pytest.raises(ValueError, match="16-kHz"):
        transcriber.transcribe("AAAA", sample_rate=48_000)

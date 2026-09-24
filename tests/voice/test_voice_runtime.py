import pytest

from voice import runtime
from voice.config import default_voice_config, load_voice_config


@pytest.mark.parametrize(
    ("configured_allocator", "expected_allocator"),
    [(None, "expandable_segments:True"), ("deployment-specific", "deployment-specific")],
)
def test_remote_gpu_server_gets_long_cold_start_window(
    tmp_path,
    monkeypatch,
    configured_allocator,
    expected_allocator,
):
    reference = tmp_path / "Eve.mp3"
    reference.write_bytes(b"voice")
    raw = default_voice_config()
    raw.update(
        {
            "engine": "eve",
            "profile": "eve-linux-gpu-server",
            "access_token": "voice-secret",
            "reference_audio": str(reference),
            "remote_core_base_url": "http://windows.test:18767/v1",
            "remote_core_api_key": "core-secret",
        }
    )
    config = load_voice_config(tmp_path, {"voice": raw})
    observed = {}

    class FakeProcess:
        returncode = None

        def poll(self):
            return self.returncode

        def terminate(self):
            self.returncode = 0

        def wait(self, timeout=None):
            return self.returncode

    class FakeProxy:
        def __init__(self, *_args):
            pass

        def start(self):
            pass

        def stop(self):
            pass

    if configured_allocator is None:
        monkeypatch.delenv("PYTORCH_CUDA_ALLOC_CONF", raising=False)
    else:
        monkeypatch.setenv("PYTORCH_CUDA_ALLOC_CONF", configured_allocator)
    monkeypatch.setattr(runtime, "build_speech_to_speech_command", lambda _config: ["voice"])
    def fake_popen(*_args, **kwargs):
        observed["environment"] = kwargs["env"]
        return FakeProcess()

    monkeypatch.setattr(runtime.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(runtime, "AuthenticatedWebSocketProxy", FakeProxy)
    monkeypatch.setattr(
        runtime,
        "_wait_for_port",
        lambda _host, _port, _process, timeout: observed.setdefault("timeout", timeout),
    )

    voice_runtime = runtime.VoiceRuntime(config)
    voice_runtime.start()
    voice_runtime.stop()

    assert observed["timeout"] == 600.0
    assert observed["environment"]["PYTORCH_CUDA_ALLOC_CONF"] == expected_allocator

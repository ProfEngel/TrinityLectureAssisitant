from platform_adapters.tts import (
    MacOSTTSBackend,
    WindowsTTSBackend,
    create_tts_backend,
)


def test_tts_factory_selects_platform_backend():
    assert isinstance(create_tts_backend("Darwin"), MacOSTTSBackend)
    assert isinstance(create_tts_backend("Windows"), WindowsTTSBackend)


def test_windows_tts_passes_text_via_environment(monkeypatch):
    backend = WindowsTTSBackend()
    backend.executable = "powershell.exe"
    captured = {}

    class FakeProcess:
        returncode = 0

        def wait(self, timeout=None):
            return 0

        def poll(self):
            return 0

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["environment"] = kwargs["env"]
        return FakeProcess()

    monkeypatch.setattr("platform_adapters.tts.subprocess.Popen", fake_popen)

    text = 'Hallo "Windows"; Remove-Item C:\\'
    backend.speak(text, voice="Katja", output_device="Lautsprecher")

    assert text not in " ".join(captured["command"])
    assert captured["environment"]["TRINITY_TTS_TEXT"] == text
    assert captured["environment"]["TRINITY_TTS_VOICE"] == "Katja"
    assert captured["environment"]["TRINITY_TTS_OUTPUT"] == "Lautsprecher"

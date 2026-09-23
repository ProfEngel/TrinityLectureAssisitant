from voice.capabilities import transcription_stream_capability


def test_legacy_and_custom_runtimes_do_not_advertise_safe_streaming(tmp_path):
    assert transcription_stream_capability(tmp_path, {}) is None
    config = {"voice": {"engine": "eve", "profile": "eve-mac-local", "speech_to_speech_executable": "custom"}}
    assert transcription_stream_capability(tmp_path, config) is None


def test_bundled_local_realtime_advertises_only_public_nonsecret_fields(tmp_path):
    config = {"voice": {"engine": "eve", "profile": "eve-mac-local", "access_token": "private"}}
    assert transcription_stream_capability(tmp_path, config) == {
        "protocol": "trinity-stt-v1", "port": 8766,
        "sample_rate": 16000, "transcription_only": True,
    }


def test_unknown_remote_runtime_keeps_compatible_http_fallback(tmp_path):
    config = {"voice": {"engine": "eve", "profile": "eve-windows-remote"}}
    assert transcription_stream_capability(tmp_path, config) is None

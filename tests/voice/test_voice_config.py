from copy import deepcopy
from pathlib import Path

from voice.config import EVE_REFERENCE_TEXT, default_voice_config, load_voice_config


def test_legacy_is_the_safe_default(tmp_path):
    config = load_voice_config(tmp_path, {})

    assert config.engine == "legacy"
    assert config.fallback_to_legacy is True
    assert config.enabled is False


def test_external_realtime_bind_requires_token(tmp_path):
    voice = default_voice_config()
    voice["engine"] = "eve"
    voice["profile"] = "eve-mac-server"
    voice["reference_audio"] = str(tmp_path / "Eve.mp3")
    Path(voice["reference_audio"]).write_bytes(b"voice")
    voice["profiles"]["eve-mac-server"]["bind_host"] = "0.0.0.0"

    config = load_voice_config(tmp_path, {"voice": voice})

    assert any("access_token" in error for error in config.validate())


def test_profile_overrides_are_merged_without_mutating_defaults(tmp_path):
    original = deepcopy(default_voice_config())
    config = load_voice_config(
        tmp_path,
        {"voice": {"profiles": {"eve-mac-local": {"public_port": 9999}}}},
        profile_name="eve-mac-local",
    )

    assert config.profile.public_port == 9999
    assert default_voice_config() == original
    assert config.reference_text == EVE_REFERENCE_TEXT


def test_local_profiles_use_realtime_barge_in_client(tmp_path):
    mac = load_voice_config(tmp_path, {}, profile_name="eve-mac-local")
    windows = load_voice_config(tmp_path, {}, profile_name="eve-windows-local")

    assert mac.profile.mode == "realtime"
    assert mac.profile.local_audio is True
    assert windows.profile.mode == "realtime"
    assert windows.profile.local_audio is True


def test_old_half_duplex_local_profile_is_migrated(tmp_path):
    config = load_voice_config(
        tmp_path,
        {
            "voice": {
                "profile": "eve-mac-local",
                "profiles": {
                    "eve-mac-local": {
                        "mode": "local",
                        "device": "mps",
                        "conversation_backend": "trinity",
                    }
                },
            }
        },
    )

    assert config.profile.mode == "realtime"
    assert config.profile.local_audio is True
    assert config.profile.device == "mps"


def test_mobile_server_profiles_bind_externally_without_desktop_audio(tmp_path):
    mac = load_voice_config(tmp_path, {}, profile_name="eve-mac-server")
    windows = load_voice_config(tmp_path, {}, profile_name="eve-windows-server")

    assert mac.profile.bind_host == "0.0.0.0"
    assert windows.profile.bind_host == "0.0.0.0"
    assert mac.profile.local_audio is False
    assert windows.profile.local_audio is False


def test_eve_requires_reference_audio(tmp_path):
    config = load_voice_config(tmp_path, {"voice": {"engine": "eve"}})

    assert any("Referenzaudio fehlt" in error for error in config.validate())


def test_documented_environment_overrides_are_supported(tmp_path, monkeypatch):
    transcript = tmp_path / "eve.txt"
    transcript.write_text("Meine lokale Eve-Stimme.", encoding="utf-8")
    audio = tmp_path / "eve.mp3"
    audio.write_bytes(b"voice")
    monkeypatch.setenv("TRINITY_EVE_VOICE_FILE", str(audio))
    monkeypatch.setenv("TRINITY_EVE_TRANSCRIPT_FILE", str(transcript))
    monkeypatch.setenv("TRINITY_VOICE_ACCESS_TOKEN", "voice-secret")
    monkeypatch.setenv("TRINITY_TTS_MODEL", "local/eve-tts")
    monkeypatch.setenv("TRINITY_LLM_BASE_URL", "http://127.0.0.1:9998/v1")
    monkeypatch.setenv("TRINITY_LLM_MODEL", "local/ornith")

    config = load_voice_config(tmp_path, {"voice": {"engine": "eve"}}, "eve-direct-ornith")

    assert config.reference_audio == audio
    assert config.reference_text == "Meine lokale Eve-Stimme."
    assert config.access_token == "voice-secret"
    assert config.profile.tts_model == "local/eve-tts"
    assert config.direct_llm_base_url == "http://127.0.0.1:9998/v1"
    assert config.direct_llm_model == "local/ornith"

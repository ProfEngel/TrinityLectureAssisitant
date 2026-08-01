import sys

from voice.command_builder import build_speech_to_speech_command
from voice.config import default_voice_config, load_voice_config


def configured_voice(tmp_path, profile="eve-mac-local"):
    reference = tmp_path / "Eve Schule.mp3"
    reference.write_bytes(b"voice")
    raw = default_voice_config()
    raw.update({
        "engine": "eve",
        "profile": profile,
        "reference_audio": str(reference),
    })
    return load_voice_config(tmp_path, {"voice": raw})


def test_command_uses_parakeet_trinity_and_eve_without_shell(tmp_path):
    config = configured_voice(tmp_path)
    command = build_speech_to_speech_command(config)

    assert command[:3] == [sys.executable, "-m", "speech_to_speech.s2s_pipeline"]
    assert command[command.index("--stt") + 1] == "parakeet-tdt"
    assert command[command.index("--llm_backend") + 1] == "chat-completions"
    assert command[command.index("--tts") + 1] == "qwen3"
    assert command[command.index("--parakeet_tdt_language") + 1] == "de"
    assert command[command.index("--qwen3_tts_language") + 1] == "German"
    assert str(config.reference_audio) in command


def test_realtime_upstream_is_forced_to_loopback(tmp_path):
    config = configured_voice(tmp_path, profile="eve-mac-server")
    command = build_speech_to_speech_command(config)

    assert command[command.index("--ws_host") + 1] == "127.0.0.1"
    assert command[command.index("--ws_port") + 1] == str(config.profile.internal_port)
    assert command[command.index("--num_pipelines") + 1] == str(config.profile.num_pipelines)


def test_windows_profile_uses_cuda_compatible_models(tmp_path):
    config = configured_voice(tmp_path, profile="eve-windows-server")
    command = build_speech_to_speech_command(config)

    assert command[command.index("--parakeet_tdt_model_name") + 1] == "nvidia/parakeet-tdt-0.6b-v3"
    assert command[command.index("--qwen3_tts_model_name") + 1] == "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
    assert command[command.index("--qwen3_tts_backend") + 1] == "torch"


def test_ubuntu_server_uses_remote_windows_trinity_core(tmp_path):
    reference = tmp_path / "Eve.mp3"
    reference.write_bytes(b"voice")
    raw = default_voice_config()
    raw.update({
        "engine": "eve",
        "profile": "eve-linux-gpu-server",
        "access_token": "voice-secret",
        "reference_audio": str(reference),
        "remote_core_base_url": "http://100.64.0.20:18767/v1",
        "remote_core_api_key": "core-secret",
    })
    config = load_voice_config(tmp_path, {"voice": raw})

    command = build_speech_to_speech_command(config)

    assert command[command.index("--responses_api_base_url") + 1] == "http://100.64.0.20:18767/v1"
    assert command[command.index("--responses_api_api_key") + 1] == "core-secret"
    assert command[command.index("--model_name") + 1] == "trinity-core"

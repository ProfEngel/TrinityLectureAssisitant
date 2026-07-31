"""Lifecycle manager for Trinity's optional Eve speech-to-speech runtime."""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

from .command_builder import build_speech_to_speech_command
from .config import VoiceConfig, load_voice_config
from .conversation import DirectLLMConversationBackend, TrinityConversationBackend
from .conversation.trinity_backend import TrinityConversationHTTPServer
from .local_realtime_client import LocalRealtimeAudioClient
from .transport import AuthenticatedWebSocketProxy


def load_runtime_config(home: str | Path, profile_name: str | None = None) -> VoiceConfig:
    root = Path(home).expanduser().resolve()
    config_path = root / "core" / "config.json"
    if config_path.is_file():
        with config_path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    else:
        raw = {}
    return load_voice_config(root, raw, profile_name=profile_name)


def _wait_for_port(host: str, port: int, process: subprocess.Popen, timeout: float = 120.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"speech-to-speech wurde mit Code {process.returncode} beendet.")
        try:
            with socket.create_connection((host, port), timeout=0.25):
                return
        except OSError:
            time.sleep(0.25)
    raise TimeoutError(f"Voice-Runtime auf {host}:{port} wurde nicht rechtzeitig bereit.")


class VoiceRuntime:
    def __init__(self, config: VoiceConfig):
        self.config = config
        self.backend_server: TrinityConversationHTTPServer | None = None
        self.proxy: AuthenticatedWebSocketProxy | None = None
        self.local_audio_client: LocalRealtimeAudioClient | None = None
        self.process: subprocess.Popen | None = None

    def start(self) -> None:
        errors = self.config.validate()
        if errors:
            raise ValueError("\n".join(errors))
        profile = self.config.profile
        if profile.conversation_backend == "trinity":
            backend = TrinityConversationBackend(self.config.home)
        else:
            backend = DirectLLMConversationBackend(
                self.config.direct_llm_base_url,
                self.config.direct_llm_model,
                self.config.direct_llm_api_key,
            )
        if profile.conversation_backend == "trinity":
            self.backend_server = TrinityConversationHTTPServer(
                backend,
                self.config.backend_host,
                self.config.backend_port,
                self.config.backend_token,
            )
            self.backend_server.start()

        command = build_speech_to_speech_command(self.config)
        env = os.environ.copy()
        env["TOKENIZERS_PARALLELISM"] = "false"
        self.process = subprocess.Popen(command, env=env)
        if profile.mode == "realtime":
            _wait_for_port("127.0.0.1", profile.internal_port, self.process)
            self.proxy = AuthenticatedWebSocketProxy(
                profile.bind_host,
                profile.public_port,
                profile.internal_port,
                self.config.access_token,
            )
            self.proxy.start()
            if profile.local_audio:
                self.local_audio_client = LocalRealtimeAudioClient(self.config)
                self.local_audio_client.start()

    def wait(self) -> int:
        if not self.process:
            return 0
        while self.process is not None and self.process.poll() is None:
            if self.local_audio_client and (
                self.local_audio_client.failure is not None
                or not self.local_audio_client.is_alive
            ):
                process = self.process
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
                return 1
            time.sleep(0.25)
        return int(self.process.returncode or 0) if self.process is not None else 0

    def stop(self) -> None:
        if self.local_audio_client:
            self.local_audio_client.stop()
            self.local_audio_client = None
        if self.proxy:
            self.proxy.stop()
            self.proxy = None
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
        self.process = None
        if self.backend_server:
            self.backend_server.stop()
            self.backend_server = None


def serve(home: str | Path, profile_name: str | None = None) -> int:
    config = load_runtime_config(home, profile_name)
    runtime = VoiceRuntime(config)
    stop_requested = False

    def request_stop(_signum, _frame):
        nonlocal stop_requested
        stop_requested = True
        runtime.stop()

    for signame in ("SIGINT", "SIGTERM"):
        if hasattr(signal, signame):
            signal.signal(getattr(signal, signame), request_stop)
    try:
        runtime.start()
        print(f"Trinity Eve Voice läuft mit Profil {config.profile.name}.")
        if config.profile.mode == "realtime":
            print(
                f"Realtime: ws://{config.profile.bind_host}:{config.profile.public_port}/v1/realtime"
            )
        return 0 if stop_requested else runtime.wait()
    finally:
        runtime.stop()


if __name__ == "__main__":
    selected_home = os.environ.get("TRINITY_HOME") or str(Path(__file__).resolve().parents[2])
    raise SystemExit(serve(selected_home, sys.argv[1] if len(sys.argv) > 1 else None))

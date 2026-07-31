"""Fast, side-effect-free diagnostics for Trinity Voice."""

from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import platform
import shutil
import socket
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.request import Request, urlopen

from .config import VoiceConfig


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str
    required: bool = True


def _package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return ""


def _port_available(host: str, port: int) -> bool:
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, int(port)))
        except OSError:
            return False
    return True


def _llm_health(base_url: str, api_key: str = "") -> tuple[bool, str]:
    url = base_url.rstrip("/") + "/models"
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        with urlopen(Request(url, headers=headers), timeout=2) as response:  # noqa: S310 - configured endpoint
            return response.status < 400, f"HTTP {response.status}"
    except Exception as exc:
        return False, type(exc).__name__


def run_checks(config: VoiceConfig) -> list[Check]:
    profile = config.profile
    s2s_version = _package_version("speech-to-speech")
    mlx_audio_version = _package_version("mlx-audio")
    checks = [
        Check("Python", sys.version_info >= (3, 10), platform.python_version()),
        Check("Engine", config.engine in {"legacy", "eve"}, config.engine),
        Check("Profil", not config.validate(), profile.name if not config.validate() else "; ".join(config.validate())),
        Check("speech-to-speech", s2s_version == "0.2.11", s2s_version or "nicht installiert"),
        Check("mlx-audio", bool(mlx_audio_version), mlx_audio_version or "nicht installiert", required=platform.system() == "Darwin"),
        Check("Parakeet-Modul", importlib.util.find_spec("speech_to_speech") is not None, config.stt_model),
        Check("Eve-Referenzaudio", config.reference_audio.is_file(), str(config.reference_audio)),
        Check("Backend-Port", _port_available(config.backend_host, config.backend_port), f"{config.backend_host}:{config.backend_port}"),
    ]
    if profile.mode == "realtime":
        checks.extend([
            Check("Interner Voice-Port", _port_available("127.0.0.1", profile.internal_port), str(profile.internal_port)),
            Check("Öffentlicher Voice-Port", _port_available(profile.bind_host, profile.public_port), f"{profile.bind_host}:{profile.public_port}"),
            Check("Realtime-Token", bool(config.access_token) or profile.bind_host in {"127.0.0.1", "localhost", "::1"}, "gesetzt" if config.access_token else "nur Loopback"),
        ])
    if profile.conversation_backend == "direct":
        ok, detail = _llm_health(config.direct_llm_base_url, config.direct_llm_api_key)
        checks.append(Check("Direktes Diagnose-LLM", ok, detail))
    checks.append(Check("Tailscale", shutil.which("tailscale") is not None, shutil.which("tailscale") or "optional", required=False))
    return checks


def doctor(config: VoiceConfig, as_json: bool = False) -> int:
    checks = run_checks(config)
    if as_json:
        print(json.dumps([asdict(item) for item in checks], ensure_ascii=False, indent=2))
    else:
        for item in checks:
            marker = "OK" if item.ok else "WARN" if not item.required else "FEHLER"
            print(f"[{marker:6}] {item.name}: {item.detail}")
    return 0 if all(item.ok or not item.required for item in checks) else 1

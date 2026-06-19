"""Shared configuration helpers for Trinity's desktop and terminal interfaces."""

import copy
import json
import os
import platform
import shutil
from pathlib import Path


def default_config(platform_name=None):
    host = platform_name or platform.system()
    windows = host == "Windows"
    return {
        "llm": {
            "active_slot": "local",
            "local": {
                "url": "http://localhost:1234/v1/chat/completions",
                "model": "",
                "api_key": "lm-studio",
            },
            "remote_1": {
                "url": "https://openrouter.ai/api/v1/chat/completions",
                "model": "",
                "api_key": "",
            },
            "remote_2": {
                "url": "https://openrouter.ai/api/v1/chat/completions",
                "model": "",
                "api_key": "",
            },
        },
        "apis": {"tavily": "", "fal_ai": ""},
        "persona": {
            "agent_name": "Trinity",
            "trigger_variants": [
                "trinity",
                "triniti",
                "trindy",
                "trinnity",
                "trinitiy",
                "trenty",
                "trendy",
            ],
        },
        "image": {
            "primary_model": "fal-ai/nano-banana-2",
            "fallback_model": "fal-ai/nano-banana-pro",
        },
        "stt": {
            "model": "small",
            "silence_threshold": 0.015,
            "chunk_duration": 6,
            "show_volume_meter": False,
        },
        "tts": {"voice": "Samantha"},
        "proactive": {
            "heartbeat_enabled": False,
            "bubbles_enabled": False,
            "visuals_enabled": False,
            "interval_minutes": 2,
            "auto_rag_indexing": False,
        },
        "system": {
            "show_terminal": windows,
            "eyes_ui_enabled": False,
            "classic_ui_enabled": True,
            "terminal_cli_enabled": windows,
            "mode": "chat",
            "windows_speech_enabled": False,
        },
        "audio_routing": {
            "private_device": "Standard",
            "public_device": "Standard",
        },
        "telegram": {"enabled": False, "bot_token": "", "chat_id": ""},
        "codex": {
            "enabled": False,
            "executable": "codex",
            "default_project": "",
            "projects": {},
            "sandbox": "workspace-write",
            "timeout_seconds": 900,
            "max_output_chars": 3200,
            "ephemeral": True,
            "network_access": False,
        },
        "opencode": {
            "enabled": False,
            "executable": "opencode",
            "default_project": "",
            "projects": {},
            "agent": "build",
            "model": "",
            "timeout_seconds": 900,
            "max_output_chars": 3200,
        },
        "comfyui": {
            "enabled": False,
            "server_url": "http://YOUR_TAILSCALE_NODE:8188",
            "default_workflow": "Flux2_Klein_T2I_API.json",
        },
        "companion": {
            "enabled": False,
            "host": "127.0.0.1",
            "port": 8765,
            "token": "",
        },
        "server": {
            "host": "127.0.0.1",
            "port": 8765,
            "token": "",
        },
    }


DEFAULT_CONFIG = default_config()


def _merge_defaults(target, defaults):
    for key, value in defaults.items():
        if key not in target:
            target[key] = copy.deepcopy(value)
        elif isinstance(value, dict) and isinstance(target.get(key), dict):
            _merge_defaults(target[key], value)
    return target


def load_config(config_path, platform_name=None):
    path = Path(config_path)
    defaults = default_config(platform_name)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            data = {}
    except (OSError, json.JSONDecodeError):
        data = {}
    return _merge_defaults(data, defaults)


def save_config(config_path, config):
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def set_config_value(config, dotted_path, value):
    parts = [part for part in dotted_path.split(".") if part]
    if not parts:
        raise ValueError("Der Einstellungspfad darf nicht leer sein.")
    current = config
    for part in parts[:-1]:
        existing = current.get(part)
        if not isinstance(existing, dict):
            existing = {}
            current[part] = existing
        current = existing
    current[parts[-1]] = value


def parse_setting_value(raw_value):
    value = str(raw_value).strip()
    lowered = value.casefold()
    if lowered in {"true", "ja", "yes", "on"}:
        return True
    if lowered in {"false", "nein", "no", "off"}:
        return False
    if lowered in {"null", "none"}:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def ensure_support_files(trinity_home):
    home = Path(trinity_home)
    core = home / "core"
    core.mkdir(parents=True, exist_ok=True)
    created = []
    for name in ("Soul.md", "User.md"):
        target = core / name
        example = core / f"{name}.example"
        if not target.exists() and example.exists():
            shutil.copy2(example, target)
            created.append(target)
    for directory in ("memory", "logs", "gen_images"):
        path = home / directory
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            created.append(path)
    return created


def find_trinity_home(explicit=None):
    candidates = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    if os.environ.get("TRINITY_HOME"):
        candidates.append(Path(os.environ["TRINITY_HOME"]).expanduser())

    candidates.extend(
        [
            Path.cwd(),
            Path(os.sys.prefix).resolve().parent,
            Path(__file__).resolve().parents[1],
            Path.home() / "Trinity_Assistant",
        ]
    )
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        candidates.append(Path(local_appdata) / "Trinity")

    for candidate in candidates:
        resolved = candidate.resolve()
        if (resolved / "trinity_launcher.py").is_file() and (
            resolved / "core"
        ).is_dir():
            return resolved
    return None

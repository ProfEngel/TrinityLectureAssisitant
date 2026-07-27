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
                "enable_thinking": False,
                "request_timeout_seconds": 120,
            },
            "remote_1": {
                "url": "https://openrouter.ai/api/v1/chat/completions",
                "model": "",
                "api_key": "",
                "request_timeout_seconds": 90,
            },
            "remote_2": {
                "url": "https://openrouter.ai/api/v1/chat/completions",
                "model": "",
                "api_key": "",
                "request_timeout_seconds": 90,
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
                "trinitys",
                "trinitie",
                "drinity",
                "trinidi",
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
            "auto_rag_indexing": True,
            "session_summary_auto_rag_indexing": True,
        },
        "system": {
            "show_terminal": windows,
            "eyes_ui_enabled": False,
            "classic_ui_enabled": True,
            "web_ui_enabled": False,
            "terminal_cli_enabled": windows,
            "mode": "chat",
            "windows_speech_enabled": False,
            "microphone_enabled": True,
            "audio_capture_mode": "mic_only",
            "tts_enabled": True,
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
            "server_url": "http://127.0.0.1:4096",
            "default_project": "",
            "projects": {},
            "agent": "build",
            "model": "",
            "timeout_seconds": 900,
            "max_output_chars": 3200,
        },
        "pi": {
            "enabled": False,
            "executable": "pi",
            "default_project": "",
            "projects": {},
            "arguments": ["-p", "{prompt}"],
            "timeout_seconds": 600,
            "max_output_chars": 3200,
        },
        "comfyui": {
            "enabled": False,
            "server_url": "http://YOUR_TAILSCALE_NODE:8188",
            "default_workflow": "Flux2_Klein_T2I_API.json",
        },
        "canvas": {
            "enabled": True,
            "install_dir": "",
            "port": 8787,
            "host": "127.0.0.1",
        },
        "companion": {
            "enabled": False,
            "host": "127.0.0.1",
            "port": 8765,
            "token": "",
        },
        "workbench": {
            "enabled": True,
            "default_harness": "opencode",
        },
        "server": {
            "host": "127.0.0.1",
            "port": 8765,
            "token": "",
            "auth_enabled": False,
        },
        "client": {
            "enabled": False,
            "server_url": "",
            "username": "",
            "token": "",
        },
        "control_plane": {
            "enabled": True,
            "runtime_root": "",
            "vault_root": "",
            "brainvault_root": "",
            "external_agents_root": "",
            "default_brainvault_harness": "pi",
            "default_mode": "guided",
            "builder_harness": "codex",
            "catalog_include_legacy": True,
        },
        "agent_catalog": {
            "default_quality_status": "unverified",
            "default_max_attempts": 2,
            "default_parallel_runs": 1,
            "agents": {
                "trinity-core": {
                    "quality_status": "stable",
                    "allowed_tools": ["llm", "memory", "stt", "tts", "payloads"],
                    "allowed_paths": ["core", "memory", "RAG", "TrinityRuntime"],
                    "requires_approval": [
                        "send_mail",
                        "delete",
                        "external_upload",
                        "publish",
                    ],
                    "max_attempts": 1,
                    "parallel_runs": 1,
                },
                "agent-builder": {
                    "quality_status": "testing",
                    "allowed_tools": ["filesystem", "tests", "harness", "job_manager"],
                    "allowed_paths": ["skills/staging", "TrinityRuntime/jobs"],
                    "requires_approval": ["activate_skill", "write_code"],
                    "max_attempts": 3,
                    "parallel_runs": 1,
                },
            },
        },
        "harness_routing": {
            "frameworks": {
                "trinity": {
                    "label": "Trinity",
                    "active": True,
                    "roles": {
                        "agent_builder": False,
                        "complex_cases": True,
                        "agent_execution": True,
                    },
                },
                "codex": {
                    "label": "Codex",
                    "active": False,
                    "roles": {
                        "agent_builder": True,
                        "complex_cases": True,
                        "agent_execution": True,
                    },
                },
                "pi": {
                    "label": "Pi",
                    "active": False,
                    "roles": {
                        "agent_builder": False,
                        "complex_cases": True,
                        "agent_execution": True,
                    },
                },
                "opencode": {
                    "label": "OpenCode",
                    "active": False,
                    "roles": {
                        "agent_builder": False,
                        "complex_cases": True,
                        "agent_execution": True,
                    },
                },
            },
            "agent_assignments": {
                "trinity-core": ["trinity"],
                "agent-builder": ["trinity", "codex"],
                "legacy-codex-agent": ["trinity", "codex"],
                "legacy-pi-agent": ["trinity", "pi"],
                "legacy-opencode-agent": ["trinity", "opencode"],
            },
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
    had_harness_routing = isinstance(data.get("harness_routing"), dict)
    raw_frameworks = (
        data.get("harness_routing", {}).get("frameworks", {})
        if had_harness_routing
        else {}
    )
    explicit_active_harnesses = {
        harness_id
        for harness_id, framework in raw_frameworks.items()
        if isinstance(framework, dict) and "active" in framework
    }
    original_assignments = None
    if had_harness_routing and isinstance(
        data.get("harness_routing", {}).get("agent_assignments"), dict
    ):
        original_assignments = copy.deepcopy(
            data["harness_routing"]["agent_assignments"]
        )
    merged = _merge_defaults(data, defaults)
    if original_assignments is not None:
        merged.setdefault("harness_routing", {})[
            "agent_assignments"
        ] = original_assignments
    return _migrate_config(
        merged,
        had_harness_routing=had_harness_routing,
        explicit_active_harnesses=explicit_active_harnesses,
    )


def _migrate_config(config, had_harness_routing=True, explicit_active_harnesses=None):
    """Keep older configs usable after schema additions."""

    _migrate_goose_to_opencode(config)
    routing = config.setdefault("harness_routing", {})
    frameworks = routing.setdefault("frameworks", {})
    defaults = DEFAULT_CONFIG["harness_routing"]
    explicit_active_harnesses = set(explicit_active_harnesses or ())
    for harness_id, default_framework in defaults["frameworks"].items():
        framework = frameworks.setdefault(harness_id, {})
        framework.setdefault("label", default_framework["label"])
        if harness_id not in explicit_active_harnesses:
            framework["active"] = (
                True
                if harness_id == "trinity"
                else bool(config.get(harness_id, {}).get("enabled", False))
            )
        else:
            framework["active"] = bool(framework.get("active", False))
        roles = framework.setdefault("roles", {})
        for role, default_value in default_framework["roles"].items():
            roles.setdefault(role, default_value)

    assignments = routing.get("agent_assignments")
    if not isinstance(assignments, dict):
        assignments = copy.deepcopy(defaults["agent_assignments"])
        routing["agent_assignments"] = assignments
    elif not had_harness_routing:
        for agent_id, harnesses in defaults["agent_assignments"].items():
            assignments.setdefault(agent_id, list(harnesses))

    # Older installations only had codex/opencode/pi enabled flags. When no
    # explicit role data existed yet, mirror those choices into the new layer.
    if had_harness_routing:
        return config

    for harness_id in ("codex", "opencode", "pi"):
        enabled = bool(config.get(harness_id, {}).get("enabled", False))
        framework = frameworks.setdefault(harness_id, {})
        roles = framework.setdefault("roles", {})
        if enabled:
            roles["complex_cases"] = True
            roles["agent_execution"] = True
            if harness_id == "codex":
                roles["agent_builder"] = True
    return config


def _migrate_goose_to_opencode(config):
    """Adopt useful legacy Goose settings, then remove Goose from active config."""

    goose = config.pop("goose", None)
    opencode = config.setdefault("opencode", {})
    if isinstance(goose, dict):
        if goose.get("enabled"):
            opencode["enabled"] = True
        goose_projects = goose.get("projects")
        if isinstance(goose_projects, dict):
            opencode_projects = opencode.setdefault("projects", {})
            if isinstance(opencode_projects, dict):
                for alias, path in goose_projects.items():
                    opencode_projects.setdefault(alias, copy.deepcopy(path))
        for key in ("default_project", "timeout_seconds", "max_output_chars"):
            current = opencode.get(key)
            empty = current in (None, "", {}, [])
            if empty and goose.get(key) not in (None, "", {}, []):
                opencode[key] = copy.deepcopy(goose[key])

    routing = config.get("harness_routing")
    if not isinstance(routing, dict):
        return
    frameworks = routing.get("frameworks")
    if isinstance(frameworks, dict):
        old = frameworks.pop("goose", None)
        current = frameworks.setdefault("opencode", {})
        if isinstance(old, dict) and old.get("active"):
            current["active"] = True
    assignments = routing.get("agent_assignments")
    if isinstance(assignments, dict):
        for agent_id, harnesses in list(assignments.items()):
            if not isinstance(harnesses, list):
                continue
            migrated = ["opencode" if item == "goose" else item for item in harnesses]
            assignments[agent_id] = list(dict.fromkeys(migrated))
        assignments.pop("legacy-goose-agent", None)


def is_harness_active(config, harness_id: str) -> bool:
    """Return the master availability flag for a configured harness."""

    harness_id = str(harness_id or "").strip().casefold()
    if harness_id == "trinity":
        return True
    frameworks = (config or {}).get("harness_routing", {}).get("frameworks", {})
    framework = frameworks.get(harness_id, {}) if isinstance(frameworks, dict) else {}
    if isinstance(framework, dict) and "active" in framework:
        return bool(framework.get("active"))
    section = (config or {}).get(harness_id, {})
    return bool(section.get("enabled", False)) if isinstance(section, dict) else False


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

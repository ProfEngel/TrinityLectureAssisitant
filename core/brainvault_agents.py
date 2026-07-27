"""Local external-agent library helpers.

External agents are shared, harness-agnostic agents installed locally outside
the Trinity repository. Trinity-internal agents stay in the repo; external
agents live under a local ``.agents`` directory and are indexed from
``agent.yaml`` files. The historic BrainVault names remain as compatibility
aliases while installations migrate away from Cloud-hosted executable code.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import time
from pathlib import Path
from typing import Iterable, Optional

from trinity_paths import TrinityPaths


BRAINVAULT_LAYOUT = (
    ".agents/_template",
    ".agents/_meta",
)
DEFAULT_HARNESSES = ["trinity", "codex", "pi", "opencode", "claude-code", "antigravity"]
AGENT_SCAN_MARKERS = {
    "agent.yaml",
    "agent.yml",
    "manifest.json",
    "SKILL.md",
    "AGENTS.md",
    "CLAUDE.md",
    "workflow.yaml",
    "workflow.yml",
    "script.py",
    "README.md",
}


def brainvault_root_from_config(home: str | Path, config: Optional[dict] = None) -> Path:
    """Resolve the local external-agent root.

    The returned path is the parent of ``.agents``. Older configurations that
    still point to a Cloud Vault remain readable, but a local ``~/.agents``
    installation takes precedence when no explicit agent root is configured.
    """

    control = (config or {}).get("control_plane", {})
    explicit = (
        control.get("external_agents_root")
        or os.environ.get("TRINITY_AGENTS_ROOT")
        or control.get("brainvault_root")
        or os.environ.get("TRINITY_BRAINVAULT")
    )
    if explicit:
        explicit_path = Path(str(explicit)).expanduser().resolve()
        if explicit_path.name == ".agents":
            return explicit_path.parent
        migrated = _migrate_legacy_agent_pool_root(explicit_path)
        return migrated or explicit_path

    paths = TrinityPaths.from_config(home, config or {})
    vault = paths.vault_root
    if vault.name.casefold() == "trinityvault":
        if vault.parent.name.casefold() == "mainhub":
            return vault.parent.parent.resolve()
        return vault.parent.resolve()
    if vault.name.casefold() == "mainhub":
        return vault.parent.resolve()
    if (vault / ".agents").is_dir():
        return vault.resolve()
    local_root = Path.home().resolve()
    return local_root


def _migrate_legacy_agent_pool_root(path: Path) -> Optional[Path]:
    """Map older MainHub/TrinityVault settings to the cleaned BrainVault root."""
    candidates: list[Path] = []
    if (path / ".agents").is_dir():
        return path
    if path.name.casefold() == "trinityvault":
        candidates.extend([path.parent.parent, path.parent])
    elif path.name.casefold() == "mainhub":
        candidates.append(path.parent)
    candidates.extend([path.parent, path.parent.parent])
    for candidate in candidates:
        if candidate and (candidate / ".agents").is_dir():
            return candidate.resolve()
    return None


def ensure_brainvault_layout(root: str | Path) -> dict:
    root_path = Path(root).expanduser().resolve()
    root_path.mkdir(parents=True, exist_ok=True)
    for relative in BRAINVAULT_LAYOUT:
        (root_path / relative).mkdir(parents=True, exist_ok=True)
    _write_if_missing(root_path / "AGENTS.md", _brainvault_agents_md())
    _write_if_missing(root_path / "CLAUDE.md", _brainvault_claude_md())
    _write_if_missing(
        root_path / ".agents" / "_meta" / ".gitignore",
        "env/*.env\nsecrets/*\n!secrets/.gitkeep\n",
    )
    _write_if_missing(root_path / ".agents" / "_meta" / "harnesses.yaml", _default_harnesses_yaml())
    _write_if_missing(root_path / ".agents" / "_meta" / "models.yaml", "profiles: []\n")
    _write_if_missing(root_path / ".agents" / "_meta" / "agent_catalog.schema.json", _catalog_schema())
    return {"root": str(root_path), "agents_dir": str(root_path / ".agents")}


def create_agent(
    root: str | Path,
    area: str,
    agent_id: str,
    *,
    name: Optional[str] = None,
    description: str = "",
    source_paths: Optional[list[str]] = None,
    status: str = "draft",
    enabled: bool = False,
) -> dict:
    root_path = Path(root).expanduser().resolve()
    ensure_brainvault_layout(root_path)
    clean_area = slugify(area or "general")
    clean_slug = slugify(agent_id or name or "agent")
    full_id = f"{clean_area}.{clean_slug.replace('-', '_')}"
    target = root_path / ".agents" / clean_area / clean_slug
    target.mkdir(parents=True, exist_ok=True)

    now = _now_date()
    display_name = name or _display_name(clean_slug)
    agent_yaml = target / "agent.yaml"
    if not agent_yaml.exists():
        data = {
            "id": full_id,
            "name": display_name,
            "version": "0.1.0",
            "source": "brainvault",
            "execution_scope": "shared_harness",
            "status": status,
            "enabled": bool(enabled),
            "created_at": now,
            "description": description or None,
            "path": f".agents/{clean_area}/{clean_slug}",
            "workspace": None,
            "triggers": {
                "natural": [display_name],
                "slash": [],
                "examples": [],
            },
            "tags": [clean_area],
            "compatible_harnesses": list(DEFAULT_HARNESSES),
            "preferred_harness": "auto",
            "entrypoints": {},
            "permissions": {
                "read": [],
                "write": [],
                "approval_required": [],
                "forbidden": ["destructive_changes_without_approval", "secret_logging"],
            },
            "secrets": [],
            "outputs": [],
            "resources": {"max_parallel_runs": 1},
            "validation": {"tests_required": True, "last_validated": None},
            "origin": {"source_paths": source_paths or []},
        }
        write_agent_yaml(agent_yaml, data)

    _write_if_missing(target / "README.md", f"# {display_name}\n\n{description or 'BrainVault-Agent im Entwurf.'}\n")
    _write_if_missing(
        target / "SKILL.md",
        f"# {display_name}\n\n## Zweck\n\n{description or 'Beschreibe hier den fachlichen Agenten.'}\n",
    )
    catalog = build_catalog(root_path)
    return {"agent_id": full_id, "path": str(target), "catalog": catalog["path"]}


def import_agent_directory(
    root: str | Path,
    source_path: str | Path,
    *,
    area: str = "skills",
    preferred_harness: str = "codex",
    status: str = "active",
    enabled: bool = True,
) -> dict:
    root_path = Path(root).expanduser().resolve()
    source = Path(source_path).expanduser().resolve()
    if not source.is_dir():
        raise FileNotFoundError(f"Agentenordner nicht gefunden: {source}")
    ensure_brainvault_layout(root_path)
    clean_area = slugify(area)
    clean_slug = slugify(source.name)
    target = root_path / ".agents" / clean_area / clean_slug
    target.mkdir(parents=True, exist_ok=True)
    copied = _copy_agent_tree(source, target)

    skill = target / "SKILL.md"
    metadata = _skill_metadata(skill)
    display_name = metadata.get("name") or _display_name(clean_slug)
    description = metadata.get("description") or f"Importierter BrainVault-Agent aus {source}"
    agent_id = f"{clean_area}.{clean_slug.replace('-', '_')}"
    scripts = sorted(
        item.relative_to(target).as_posix()
        for item in target.rglob("*.py")
        if "__pycache__" not in item.parts and ".venv" not in item.parts
    )
    entrypoints = {}
    if (target / "workflow.yaml").is_file():
        entrypoints["workflow"] = "workflow.yaml"
    elif (target / "workflow.yml").is_file():
        entrypoints["workflow"] = "workflow.yml"
    if (target / "script.py").is_file():
        entrypoints["script"] = "script.py"
    elif scripts:
        entrypoints["script"] = scripts[0]

    data = {
        "id": agent_id,
        "name": display_name,
        "version": "1.0.0",
        "source": "brainvault",
        "execution_scope": "shared_harness",
        "status": status,
        "enabled": bool(enabled),
        "created_at": _now_date(),
        "description": description,
        "path": f".agents/{clean_area}/{clean_slug}",
        "workspace": None,
        "triggers": {
            "natural": [display_name, clean_slug.replace("-", " ")],
            "slash": [],
            "examples": [f"Trinity, nutze den {display_name} Agenten."],
        },
        "tags": [clean_area, "campushub"],
        "compatible_harnesses": list(DEFAULT_HARNESSES),
        "preferred_harness": preferred_harness or "auto",
        "entrypoints": entrypoints,
        "permissions": {
            "read": [],
            "write": [],
            "approval_required": ["activate_skill"] if status != "active" else [],
            "forbidden": ["destructive_changes_without_approval", "secret_logging"],
        },
        "secrets": [],
        "outputs": [],
        "resources": {"max_parallel_runs": 1},
        "validation": {"tests_required": False, "last_validated": _now_date() if status == "active" else None},
        "origin": {"source_paths": [str(source)]},
    }
    write_agent_yaml(target / "agent.yaml", data)
    _write_if_missing(target / "README.md", f"# {display_name}\n\n{description}\n")
    if not skill.is_file():
        (target / "SKILL.md").write_text(f"# {display_name}\n\n{description}\n", encoding="utf-8")
    catalog = build_catalog(root_path)
    return {
        "agent_id": agent_id,
        "path": str(target),
        "copied_files": copied,
        "catalog": catalog["path"],
    }


def register_external_agent(
    root: str | Path,
    source_path: str | Path,
    *,
    area: str = "external",
    agent_id: str = "",
    name: str = "",
    description: str = "",
    preferred_harness: str = "codex",
    status: str = "active",
    enabled: bool = True,
    kind: str = "project",
    workspace: str = "",
    entrypoint: str = "",
    parent_agent: str = "",
    tags: Optional[list[str]] = None,
    copy_source: bool = False,
) -> dict:
    """Register an existing external file or project as a BrainVault agent.

    Unlike import_agent_directory, this can keep large project folders in place
    and only stores a clean BrainVault manifest plus optional source snapshot.
    """

    root_path = Path(root).expanduser().resolve()
    source = Path(source_path).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"Quelle nicht gefunden: {source}")
    ensure_brainvault_layout(root_path)
    clean_area = slugify(area or "external")
    clean_slug = slugify(agent_id or source.stem or source.name)
    full_id = f"{clean_area}.{clean_slug.replace('-', '_')}"
    target = root_path / ".agents" / clean_area / clean_slug
    target.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    if copy_source:
        copied = _copy_source_snapshot(source, target / "source")

    display_name = name or _display_name(clean_slug)
    desc = description or f"Externer Harness-Agent aus {source}"
    workspace_value = str(Path(workspace).expanduser().resolve()) if workspace else str(source if source.is_dir() else source.parent)
    source_relative = ""
    if copied:
        source_relative = copied[0] if len(copied) == 1 else "source"
    entrypoints = {}
    if entrypoint:
        entrypoints["primary"] = entrypoint
    elif source.is_file():
        entrypoints["primary"] = source.name
    if source.suffix == ".py":
        entrypoints["script"] = source.name
    elif source.suffix in {".html", ".htm"}:
        entrypoints["html"] = source.name
    elif source.suffix.lower() == ".md":
        entrypoints["markdown"] = source.name
    if source_relative:
        entrypoints["source_snapshot"] = source_relative

    natural = [display_name, clean_slug.replace("-", " ")]
    if parent_agent:
        natural.append(parent_agent)
    data = {
        "id": full_id,
        "name": display_name,
        "version": "1.0.0",
        "source": "brainvault",
        "execution_scope": "shared_harness",
        "status": status,
        "enabled": bool(enabled),
        "created_at": _now_date(),
        "description": desc,
        "path": f".agents/{clean_area}/{clean_slug}",
        "workspace": workspace_value,
        "kind": kind,
        "parent_agent": parent_agent,
        "triggers": {
            "natural": natural,
            "slash": [],
            "examples": [f"Trinity, nutze den {display_name} Agenten."],
        },
        "tags": list(dict.fromkeys([clean_area, kind, *(tags or [])])),
        "compatible_harnesses": list(DEFAULT_HARNESSES),
        "preferred_harness": preferred_harness or "auto",
        "entrypoints": entrypoints,
        "permissions": {
            "read": [str(source)],
            "write": [workspace_value],
            "approval_required": ["external_write"] if status == "active" else ["activate_skill"],
            "forbidden": ["destructive_changes_without_approval", "secret_logging"],
        },
        "secrets": [],
        "outputs": [],
        "resources": {"max_parallel_runs": 1},
        "validation": {"tests_required": False, "last_validated": _now_date() if status == "active" else None},
        "origin": {"source_paths": [str(source)]},
    }
    write_agent_yaml(target / "agent.yaml", data)
    (target / "README.md").write_text(_external_readme(display_name, desc, source, copied), encoding="utf-8")
    (target / "SKILL.md").write_text(
        _external_skill(display_name, desc, source, kind, parent_agent, entrypoints),
        encoding="utf-8",
    )
    catalog = build_catalog(root_path)
    return {
        "agent_id": full_id,
        "path": str(target),
        "copied_files": copied,
        "catalog": catalog["path"],
    }


def build_catalog(root: str | Path) -> dict:
    root_path = Path(root).expanduser().resolve()
    ensure_brainvault_layout(root_path)
    agents = []
    for yaml_path in iter_agent_files(root_path):
        data = load_agent_yaml(yaml_path)
        if not data:
            continue
        record = _catalog_record(root_path, yaml_path, data)
        agents.append(record)
    agents.sort(key=lambda item: (str(item.get("area", "")), str(item.get("id", ""))))
    catalog = {
        "schema_version": 1,
        "generated_at": _now_timestamp(),
        "source": "brainvault",
        "root": str(root_path),
        "summary": {
            "total": len(agents),
            "draft": sum(1 for item in agents if item.get("status") == "draft"),
            "active": sum(1 for item in agents if item.get("status") == "active"),
            "enabled": sum(1 for item in agents if item.get("enabled") is True),
        },
        "agents": agents,
    }
    catalog_dir = root_path / ".agents" / "_meta"
    catalog_dir.mkdir(parents=True, exist_ok=True)
    catalog_path = catalog_dir / "agent_catalog.json"
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (catalog_dir / "AGENT_CATALOG.md").write_text(_catalog_markdown(catalog), encoding="utf-8")
    _write_if_missing(catalog_dir / "agent_catalog.schema.json", _catalog_schema())
    return {"path": str(catalog_path), "summary": catalog["summary"], "agents": agents}


def validate_agent(root: str | Path, agent_id: str) -> dict:
    found = find_agent(root, agent_id)
    if not found:
        return {"ok": False, "errors": [f"Agent nicht gefunden: {agent_id}"], "warnings": []}
    yaml_path, data = found
    errors = []
    warnings = []
    for key in ("id", "name", "source", "execution_scope", "status", "path"):
        if not data.get(key):
            errors.append(f"agent.yaml: Feld fehlt: {key}")
    if data.get("source") != "brainvault":
        errors.append("agent.yaml: source muss brainvault sein.")
    if data.get("execution_scope") != "shared_harness":
        errors.append("agent.yaml: execution_scope muss shared_harness sein.")
    if data.get("status") not in {"draft", "active", "disabled", "archived"}:
        errors.append("agent.yaml: status ist ungueltig.")
    agent_dir = yaml_path.parent
    if not (agent_dir / "SKILL.md").is_file():
        warnings.append("SKILL.md fehlt.")
    if not (agent_dir / "README.md").is_file():
        warnings.append("README.md fehlt.")
    validation = data.get("validation") or {}
    if validation.get("tests_required") and not (agent_dir / "tests").is_dir():
        warnings.append("tests_required ist aktiv, aber tests/ fehlt.")
    origin = data.get("origin") if isinstance(data.get("origin"), dict) else {}
    for source_path in origin.get("source_paths") or []:
        if source_path and not Path(str(source_path)).expanduser().exists():
            errors.append(f"Ursprungspfad fehlt: {source_path}")
    for script in agent_dir.rglob("*.py"):
        if any(part in {".venv", "__pycache__"} for part in script.parts):
            continue
        try:
            import py_compile

            py_compile.compile(str(script), doraise=True)
        except Exception as exc:
            errors.append(f"Python-Syntaxfehler in {script.relative_to(agent_dir)}: {exc}")
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "path": str(yaml_path),
        "agent": _catalog_record(Path(root).expanduser().resolve(), yaml_path, data),
    }


def inspect_agent(root: str | Path, agent_id: str) -> Optional[dict]:
    found = find_agent(root, agent_id)
    if not found:
        return None
    yaml_path, data = found
    return _catalog_record(Path(root).expanduser().resolve(), yaml_path, data)


def list_agents(root: str | Path) -> list[dict]:
    return build_catalog(root)["agents"]


def find_agent(root: str | Path, agent_id: str) -> Optional[tuple[Path, dict]]:
    wanted = str(agent_id or "").casefold()
    for yaml_path in iter_agent_files(root):
        data = load_agent_yaml(yaml_path)
        candidates = {
            str(data.get("id", "")).casefold(),
            yaml_path.parent.name.casefold(),
            f"{yaml_path.parent.parent.name}.{yaml_path.parent.name}".casefold(),
        }
        if wanted in candidates:
            return yaml_path, data
    return None


def iter_agent_files(root: str | Path) -> Iterable[Path]:
    agents_root = Path(root).expanduser().resolve() / ".agents"
    if not agents_root.is_dir():
        return []
    return sorted(list(agents_root.rglob("agent.yaml")) + list(agents_root.rglob("agent.yml")))


def audit_candidates(search_roots: list[str | Path], output_path: str | Path) -> dict:
    candidates = []
    seen_dirs = set()
    for root in search_roots:
        root_path = Path(root).expanduser()
        if not root_path.exists():
            continue
        for path in root_path.rglob("*"):
            if not path.is_file() or path.name not in AGENT_SCAN_MARKERS:
                continue
            if any(part in {"node_modules", "__pycache__", ".git"} for part in path.parts):
                continue
            directory = path.parent.resolve()
            if directory in seen_dirs:
                continue
            seen_dirs.add(directory)
            candidates.append(_audit_candidate(root_path, directory))
    output = Path(output_path).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_audit_markdown(candidates), encoding="utf-8")
    return {"path": str(output), "count": len(candidates)}


def load_agent_yaml(path: str | Path) -> dict:
    text = Path(path).read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text)
        return data if isinstance(data, dict) else {}
    except Exception:
        return _simple_yaml_load(text)


def write_agent_yaml(path: str | Path, data: dict) -> None:
    Path(path).write_text(_simple_yaml_dump(data), encoding="utf-8")


def slugify(value: str) -> str:
    value = str(value or "agent").strip().casefold()
    value = (
        value.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )
    slug = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return slug[:64] or "agent"


def _catalog_record(root: Path, yaml_path: Path, data: dict) -> dict:
    relative_path = yaml_path.parent.relative_to(root).as_posix()
    area = yaml_path.parent.parent.name if yaml_path.parent.parent.name != ".agents" else ""
    triggers = data.get("triggers") if isinstance(data.get("triggers"), dict) else {}
    permissions = data.get("permissions") if isinstance(data.get("permissions"), dict) else {}
    validation = data.get("validation") if isinstance(data.get("validation"), dict) else {}
    return {
        "id": data.get("id", ""),
        "name": data.get("name", ""),
        "version": data.get("version", ""),
        "status": data.get("status", ""),
        "enabled": bool(data.get("enabled", False)),
        "source": data.get("source", ""),
        "execution_scope": data.get("execution_scope", ""),
        "description": data.get("description", ""),
        "area": area,
        "path": relative_path,
        "absolute_path": str(yaml_path.parent),
        "workspace": data.get("workspace"),
        "tags": data.get("tags") or [],
        "natural_triggers": triggers.get("natural", []),
        "slash_triggers": triggers.get("slash", []),
        "examples": triggers.get("examples", []),
        "compatible_harnesses": data.get("compatible_harnesses") or [],
        "preferred_harness": data.get("preferred_harness", "auto"),
        "entrypoints": data.get("entrypoints") or {},
        "kind": data.get("kind", ""),
        "parent_agent": data.get("parent_agent", ""),
        "permissions": permissions,
        "approval_required": permissions.get("approval_required", []),
        "forbidden": permissions.get("forbidden", []),
        "secrets": data.get("secrets") or [],
        "outputs": data.get("outputs") or [],
        "tests_required": bool(validation.get("tests_required", False)),
        "last_validated": _json_scalar(validation.get("last_validated")),
        "origin": data.get("origin") or {},
        "updated_at": _json_scalar(data.get("updated_at") or data.get("created_at")),
    }


def _json_scalar(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _simple_yaml_dump(value, indent: int = 0) -> str:
    lines = []
    prefix = " " * indent
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.append(_simple_yaml_dump(item, indent + 2).rstrip())
            else:
                lines.append(f"{prefix}{key}: {_yaml_scalar(item)}")
    elif isinstance(value, list):
        if not value:
            lines.append(f"{prefix}[]")
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.append(_simple_yaml_dump(item, indent + 2).rstrip())
            else:
                lines.append(f"{prefix}- {_yaml_scalar(item)}")
    else:
        lines.append(f"{prefix}{_yaml_scalar(value)}")
    return "\n".join(line for line in lines if line is not None) + "\n"


def _yaml_scalar(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if not text:
        return '""'
    if re.search(r"[:#\n\[\]{}]|^\s|\s$", text) or text.lower() in {"true", "false", "null"}:
        return json.dumps(text, ensure_ascii=False)
    return text


def _simple_yaml_load(text: str) -> dict:
    raw_lines = [
        line.rstrip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    def indent_of(line: str) -> int:
        return len(line) - len(line.lstrip(" "))

    def parse_block(index: int, indent: int):
        if index >= len(raw_lines):
            return {}, index
        is_list = raw_lines[index].strip().startswith("-")
        container = [] if is_list else {}
        while index < len(raw_lines):
            line = raw_lines[index]
            current_indent = indent_of(line)
            if current_indent < indent:
                break
            if current_indent > indent:
                index += 1
                continue
            stripped = line.strip()
            if is_list:
                if not stripped.startswith("-"):
                    break
                item_text = stripped[1:].strip()
                if not item_text:
                    value, index = parse_block(index + 1, indent + 2)
                    container.append(value)
                    continue
                if ":" in item_text and not item_text.startswith('"'):
                    key, raw_value = item_text.split(":", 1)
                    item = {}
                    raw_value = raw_value.strip()
                    if raw_value:
                        item[key.strip()] = _parse_scalar(raw_value)
                        index += 1
                    else:
                        value, index = parse_block(index + 1, indent + 2)
                        item[key.strip()] = value
                    container.append(item)
                    continue
                container.append(_parse_scalar(item_text))
                index += 1
                continue
            if stripped.startswith("-") or ":" not in stripped:
                break
            key, raw_value = stripped.split(":", 1)
            raw_value = raw_value.strip()
            if raw_value:
                container[key.strip()] = _parse_scalar(raw_value)
                index += 1
            else:
                value, index = parse_block(index + 1, indent + 2)
                container[key.strip()] = value
        return container, index

    parsed, _ = parse_block(0, 0)
    return parsed if isinstance(parsed, dict) else {}


def _parse_scalar(value: str):
    if value == "[]":
        return []
    if value in {"null", "~"}:
        return None
    if value == "true":
        return True
    if value == "false":
        return False
    if value.startswith('"') and value.endswith('"'):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value.strip('"')
    return value


def _catalog_markdown(catalog: dict) -> str:
    lines = [
        "# BrainVault Agent Catalog",
        "",
        f"Generated: {catalog.get('generated_at', '')}",
        "",
        "| ID | Name | Status | Enabled | Harnesses | Path |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for agent in catalog.get("agents", []):
        harnesses = ", ".join(agent.get("compatible_harnesses") or [])
        lines.append(
            "| {id} | {name} | {status} | {enabled} | {harnesses} | {path} |".format(
                id=agent.get("id", ""),
                name=str(agent.get("name", "")).replace("|", "\\|"),
                status=agent.get("status", ""),
                enabled="yes" if agent.get("enabled") else "no",
                harnesses=harnesses,
                path=agent.get("path", ""),
            )
        )
    return "\n".join(lines) + "\n"


def _audit_candidate(root: Path, directory: Path) -> dict:
    files = {path.name for path in directory.iterdir() if path.is_file()}
    tests = (directory / "tests").is_dir() or any(name.startswith("test_") for name in files)
    entry = next((name for name in ("agent.yaml", "agent.yml", "manifest.json", "SKILL.md", "AGENTS.md", "workflow.yaml", "script.py", "README.md") if name in files), "")
    origin = "trinity" if "Trinity_Assistant" in directory.parts else "brainvault"
    recommendation = "unveraendert lassen" if origin == "trinity" else "migrieren/pruefen"
    return {
        "path": str(directory),
        "function": directory.name.replace("-", " ").replace("_", " "),
        "entry": entry,
        "tests": tests,
        "dependencies": sorted(name for name in files if name in {"requirements.txt", "pyproject.toml", "package.json"}),
        "target_area": slugify(directory.parent.name),
        "duplicates": [],
        "origin": origin,
        "classification": "Trinity-intern" if origin == "trinity" else "BrainVault-extern",
        "recommendation": recommendation,
    }


def _copy_agent_tree(source: Path, target: Path) -> list[str]:
    copied = []
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        if any(part in {".git", ".venv", "__pycache__", "node_modules", ".mypy_cache", ".pytest_cache"} for part in relative.parts):
            continue
        if any(part.startswith(".") and part not in {".obsidian"} for part in relative.parts):
            continue
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        copied.append(relative.as_posix())
    return copied


def _copy_source_snapshot(source: Path, target: Path) -> list[str]:
    if target.exists():
        shutil.rmtree(target)
    if source.is_file():
        target.mkdir(parents=True, exist_ok=True)
        destination = target / source.name
        shutil.copy2(source, destination)
        return [destination.relative_to(target.parent).as_posix()]
    target.mkdir(parents=True, exist_ok=True)
    return [f"source/{item}" for item in _copy_agent_tree(source, target)]


def _skill_metadata(path: Path) -> dict:
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8", errors="ignore")
    metadata = {}
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for line in lines[1:]:
            if line.strip() == "---":
                break
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip().strip('"')
    if not metadata.get("name"):
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("# "):
                metadata["name"] = stripped[2:].strip()
                break
    return metadata


def _external_readme(display_name: str, description: str, source: Path, copied: list[str]) -> str:
    lines = [
        f"# {display_name}",
        "",
        description,
        "",
        f"- Ursprung: `{source}`",
        f"- Snapshot: {'ja' if copied else 'nein, Quelle bleibt am Ursprungspfad'}",
    ]
    if copied:
        lines.extend(["", "## Kopierte Dateien", ""])
        lines.extend(f"- `{item}`" for item in copied[:80])
        if len(copied) > 80:
            lines.append(f"- ... {len(copied) - 80} weitere Dateien")
    return "\n".join(lines) + "\n"


def _external_skill(
    display_name: str,
    description: str,
    source: Path,
    kind: str,
    parent_agent: str,
    entrypoints: dict,
) -> str:
    lines = [
        f"# {display_name}",
        "",
        "## Zweck",
        "",
        description,
        "",
        "## Harness-Nutzung",
        "",
        "- Lies zuerst `agent.yaml`.",
        "- Arbeite innerhalb der dort genannten `permissions` und Ursprungspfade.",
        "- Keine destruktiven Aenderungen ohne ausdrueckliche Freigabe.",
        "- Ergebnisse und Berichte im freigegebenen Workspace oder Ergebnisordner ablegen.",
        "",
        "## Quelle",
        "",
        f"- Typ: `{kind}`",
        f"- Ursprung: `{source}`",
    ]
    if parent_agent:
        lines.append(f"- Uebergeordneter Agent: `{parent_agent}`")
    if entrypoints:
        lines.extend(["", "## Einstiegspunkte", ""])
        lines.extend(f"- `{key}`: `{value}`" for key, value in entrypoints.items())
    return "\n".join(lines) + "\n"


def _audit_markdown(candidates: list[dict]) -> str:
    lines = ["# BrainVault Agent Audit", "", f"Gefundene Kandidaten: {len(candidates)}", ""]
    for item in candidates:
        lines.extend(
            [
                f"## {item['function']}",
                "",
                f"- bisheriger Pfad: `{item['path']}`",
                f"- vermutete Funktion: {item['function']}",
                f"- erkannte Einstiegsdatei: {item['entry'] or 'unbekannt'}",
                f"- vorhandene Tests: {'ja' if item['tests'] else 'nein/unklar'}",
                f"- Abhängigkeiten: {', '.join(item['dependencies']) or 'keine erkannt'}",
                f"- mögliche Zielkategorie: {item['target_area']}",
                f"- mögliche Duplikate: {', '.join(item['duplicates']) or 'nicht geprüft'}",
                f"- Herkunft: {item['origin']}",
                f"- Einordnung: {item['classification']}",
                f"- Empfehlung: {item['recommendation']}",
                "",
            ]
        )
    return "\n".join(lines)


def _brainvault_agents_md() -> str:
    return """# Regeln fuer den lokalen Agenten-Werkzeugkasten

- Die lokale Ablage .agents ist die einzige ausfuehrbare Quelle gemeinsamer externer Agenten.
- Trinity-interne Agenten bleiben ausschliesslich im Trinity-Repository.
- Jeder neue externe Agent wird direkt unter der lokalen Ablage .agents angelegt.
- Der BrainVault enthaelt Inhalte, aber keinen ausfuehrbaren Agentencode.
- Neue Agenten erscheinen sofort als draft im Katalog.
- Vor Änderungen zuerst agent.yaml, SKILL.md und vorhandene Tests lesen.
- Keine Agenten duplizieren.
- Bestehende Agenten bei Erweiterungen versionieren.
- Nach jeder Änderung den Katalog neu generieren.
- Ergebnisdateien nur im erlaubten Workspace oder Ergebnisbereich ablegen.
- Keine destruktiven Änderungen ohne Freigabe.
- Secrets nur ueber definierte .env-/Secret-Referenzen nutzen.
- Secret-Werte nie in Logs, Katalogen, Reports oder Git-Repositories schreiben.
- Harness-spezifische Adapter nur ergaenzen, wenn sie wirklich erforderlich sind.
"""


def _brainvault_claude_md() -> str:
    return """# Claude Code Notes

Dieser lokale Agenten-Werkzeugkasten folgt AGENTS.md. Claude Code soll vor
jeder Arbeit an externen Agenten zuerst AGENTS.md und die jeweilige agent.yaml
lesen.
"""


def _default_harnesses_yaml() -> str:
    return """harnesses:
  - id: trinity
    role: control-plane
    default_for: [routing, user-facing-orchestration]
  - id: pi
    role: default-agent-runtime
    default_for: [brainvault-agent-execution, analysis, drafts, reports]
    path_policy: relative-first
  - id: codex
    role: agent-builder
    default_for: [new-agent-creation, agent-refactoring, tests, quality-gates]
  - id: opencode
    role: optional-runtime
  - id: claude-code
    role: optional-builder
  - id: antigravity
    role: direct-human-workbench
defaults:
  external_agent_runtime: pi
  agent_builder: codex
  direct_workbench: antigravity
"""


def _catalog_schema() -> str:
    return json.dumps(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "BrainVault Agent Catalog",
            "type": "object",
            "required": ["schema_version", "agents"],
            "properties": {
                "schema_version": {"type": "integer"},
                "agents": {"type": "array"},
            },
        },
        ensure_ascii=False,
        indent=2,
    ) + "\n"


def _write_if_missing(path: Path, content: str) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _display_name(slug: str) -> str:
    return " ".join(part.capitalize() for part in str(slug).replace("_", "-").split("-") if part)


def _now_date() -> str:
    return time.strftime("%Y-%m-%d")


def _now_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")

"""Bridge from Trinity to the locally installed Goose CLI."""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path

from configuration import is_harness_active
from platform_adapters import find_goose_executable


PRIORITY = 96

TRIGGER_PATTERNS = (
    r"\b(?:nutze|starte|frage|frag|verwende)\s+goose\b",
    r"\bgoose[- ]?(?:agent|cli)\b",
)


def can_handle(query: str) -> bool:
    text = str(query or "").casefold()
    return any(re.search(pattern, text) for pattern in TRIGGER_PATTERNS)


def execute(query: str, context: dict | None = None) -> dict:
    context = context or {}
    config = dict(context.get("goose_cfg") or {})
    full_config = _config_from_context(context, config)

    if not is_harness_active(full_config, "goose") or not config.get("enabled", False):
        return _result(
            "Goose ist noch nicht aktiviert. Öffne Einstellungen > Harnesses, "
            "schalte Goose auf Aktiv und erlaube anschließend Goose-Aufträge."
        )

    executable = _resolve_executable(config.get("executable", "goose"))
    if not executable:
        return _result(
            "Goose wurde nicht als CLI gefunden. Installiere Goose oder trage "
            "unter Einstellungen > Harnesses > Goose den vollständigen Programmpfad ein."
        )

    projects = _configured_projects(config)
    alias, project_path, error = _select_project(query, projects, config)
    if error:
        return _result(error)

    prompt = _build_prompt(query, alias, project_path)
    timeout = _bounded_int(config.get("timeout_seconds"), 900, 30, 7200)
    arguments = _normalize_arguments(config.get("arguments"))
    try:
        answer = _run_goose(
            executable=executable,
            arguments=arguments,
            prompt=prompt,
            timeout=timeout,
            project_path=project_path,
            project_alias=alias,
        )
    except subprocess.TimeoutExpired:
        return _result(f"Goose hat das Zeitlimit von {timeout} Sekunden überschritten.", alias)
    except OSError as exc:
        return _result(f"Goose konnte nicht gestartet werden: {exc}", alias)

    answer = _truncate(answer.strip(), _bounded_int(config.get("max_output_chars"), 3200, 500, 12000))
    if not answer:
        answer = "Goose hat den Lauf beendet, aber keinen Abschlussbericht zurückgegeben."
    return _result(answer, alias)


def _configured_projects(config: dict) -> dict[str, Path]:
    projects = config.get("projects", {})
    if not isinstance(projects, dict):
        return {}
    result = {}
    for alias, raw_path in projects.items():
        alias = str(alias).strip()
        if not alias or not raw_path:
            continue
        path = Path(os.path.expandvars(os.path.expanduser(str(raw_path)))).resolve()
        if path.is_dir():
            result[alias] = path
    return result


def _select_project(query: str, projects: dict[str, Path], config: dict):
    if not projects:
        return "", None, (
            "Für Goose ist noch kein Projekt freigegeben. Lege unter Harnesses > Goose "
            "mindestens einen Alias mit Ordnerpfad an."
        )
    text = str(query or "").casefold()
    for alias in sorted(projects, key=len, reverse=True):
        escaped = re.escape(alias.casefold())
        if re.search(rf"\b(?:projekt\s+)?[\"'„“]?{escaped}(?:\b|[\"'“])", text):
            return alias, projects[alias], None
    default_alias = str(config.get("default_project", "")).strip()
    for alias, path in projects.items():
        if alias.casefold() == default_alias.casefold():
            return alias, path, None
    if len(projects) == 1:
        alias = next(iter(projects))
        return alias, projects[alias], None
    return "", None, (
        "Bitte nenne das Goose-Projekt. Freigegeben sind: "
        + ", ".join(sorted(projects))
        + "."
    )


def _resolve_executable(raw_executable: str) -> str | None:
    value = os.path.expandvars(os.path.expanduser(str(raw_executable or "goose").strip()))
    if os.path.dirname(value):
        return value if Path(value).is_file() else None
    if value.casefold() in {"goose", "goose.exe", "goose.cmd"}:
        return find_goose_executable()
    return shutil.which(value)


def _normalize_arguments(value) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return shlex.split(value)
    return ["run", "--no-session", "--quiet", "--text", "{prompt}"]


def _run_goose(
    *,
    executable: str,
    arguments: list[str],
    prompt: str,
    timeout: int,
    project_path: Path,
    project_alias: str,
) -> str:
    has_prompt = any("{prompt}" in item for item in arguments)
    command = [executable, *[item.replace("{prompt}", prompt) for item in arguments]]
    if not has_prompt:
        command.append(prompt)
    use_shell = os.name == "nt" and executable.casefold().endswith((".cmd", ".bat"))
    run_command = subprocess.list2cmdline(command) if use_shell else command
    env = dict(os.environ)
    env.setdefault("NO_COLOR", "1")
    env["TRINITY_PROJECT_ROOT"] = str(project_path)
    env["TRINITY_PROJECT_ALIAS"] = project_alias
    completed = subprocess.run(
        run_command,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
        shell=use_shell,
        cwd=str(project_path),
        env=env,
    )
    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout or "").strip()
        raise OSError(f"Goose wurde mit Fehlercode {completed.returncode} beendet. {_truncate(details, 1200)}")
    return completed.stdout


def _build_prompt(query: str, alias: str, project_path: Path) -> str:
    return f"""Du wurdest von Trinity als lokaler Goose-Harness gestartet.

Projekt: {alias}
Arbeitsordner: {project_path}
Auftrag des Nutzers:
{query.strip()}

Arbeite nur im freigegebenen Projektordner und beachte dort AGENTS.md, .agents,
README und Projektregeln. Du darfst Dateien, Agenten und Tests nur dort anlegen oder
ändern, wenn der Auftrag dies verlangt.

Sicherheitsregeln:
- Keine Nachrichten, E-Mails oder Daten an Dritte senden; nur Entwürfe vorbereiten.
- Keine Pushes, Deployments, Käufe, Löschungen oder externen Uploads ausführen.
- Für BrainVault-Agenten sind Analyse, Staging, Tests und Katalogpflege erlaubt;
  produktive Freigaben bleiben beim Nutzer.
- Antworte auf Deutsch mit erledigten Schritten, geänderten Dateien, Prüfstatus und
  eventuellen Blockern.
"""


def _config_from_context(context: dict, fallback: dict) -> dict:
    supplied = context.get("full_config") if isinstance(context, dict) else None
    if isinstance(supplied, dict):
        return supplied
    brain = context.get("brain")
    config_path = getattr(brain, "config_path", "") if brain is not None else ""
    if config_path:
        try:
            import json

            data = json.loads(Path(config_path).read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (OSError, ValueError):
            pass
    return {"goose": fallback, "harness_routing": {"frameworks": {"goose": {"active": True}}}}


def _result(message: str, alias: str = "") -> dict:
    title = "Goose" + (f" · {alias}" if alias else "")
    return {
        "has_payload": False,
        "html_payload": "",
        "search_context": "",
        "direct_answer": f"{title}\n\n{message}",
    }


def _truncate(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: max(0, limit - 80)].rstrip() + "\n\n[Bericht gekürzt.]"


def _bounded_int(value, default: int, minimum: int, maximum: int) -> int:
    try:
        return max(minimum, min(maximum, int(value)))
    except (TypeError, ValueError):
        return default

"""Generic bridge from Trinity to a user-provided Pi CLI wrapper."""

from __future__ import annotations

import html
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path

from platform_adapters import find_pi_executable


PRIORITY = 97

TRIGGER_PATTERNS = (
    r"\b(?:nutze|starte|frage|verwende)\s+pi\b",
    r"\bpi[- ]agent\b",
    r"\bpi[- ]cli\b",
)


def can_handle(query: str) -> bool:
    text = query.casefold()
    return any(re.search(pattern, text) for pattern in TRIGGER_PATTERNS)


def execute(query: str, context: dict = None) -> dict:
    context = context or {}
    config = dict(context.get("pi_cfg") or {})

    if not config.get("enabled", False):
        return _result(
            "Der Pi-Agent ist noch nicht aktiviert. Trage im Trinity-Setup eine "
            "Pi-CLI oder einen eigenen Pi-Wrapper ein und aktiviere den Agenten."
        )

    executable = _resolve_executable(config.get("executable", "pi"))
    if not executable:
        return _result(
            "Pi wurde auf diesem Rechner nicht als CLI gefunden. Wenn Du Pi über "
            "einen eigenen Wrapper nutzt, trage dessen vollständigen Pfad in den "
            "Pi-Einstellungen ein."
        )

    projects = _configured_projects(config)
    if _is_project_list_request(query):
        return _project_list_result(projects, config.get("default_project", ""))

    alias, project_path, error = _select_project(query, projects, config)
    if error:
        return _result(error)

    timeout = _bounded_int(config.get("timeout_seconds"), 600, 30, 3600)
    arguments = _normalize_arguments(config.get("arguments", []))
    prompt = _build_prompt(query, alias, project_path)

    try:
        answer = _run_pi(
            executable=executable,
            arguments=arguments,
            prompt=prompt,
            timeout=timeout,
            project_path=project_path,
        )
    except subprocess.TimeoutExpired:
        return _result(f"Pi hat das Zeitlimit von {timeout} Sekunden überschritten.")
    except OSError as exc:
        return _result(f"Pi konnte nicht gestartet werden: {exc}")

    max_chars = _bounded_int(config.get("max_output_chars"), 3200, 500, 12000)
    answer = _truncate(answer.strip(), max_chars)
    if not answer:
        answer = "Pi hat den Lauf beendet, aber keine Antwort zurückgegeben."
    return _result(answer, alias)


def _configured_projects(config: dict) -> dict:
    projects = config.get("projects", {})
    if not isinstance(projects, dict):
        return {}

    result = {}
    for alias, raw_path in projects.items():
        clean_alias = str(alias).strip()
        if not clean_alias or not raw_path:
            continue
        path = Path(os.path.expandvars(os.path.expanduser(str(raw_path)))).resolve()
        if path.is_dir():
            result[clean_alias] = path
    return result


def _select_project(query: str, projects: dict, config: dict):
    text = query.casefold()
    if projects:
        matches = []
        for alias in sorted(projects, key=len, reverse=True):
            escaped_alias = re.escape(alias.casefold())
            patterns = (
                rf"\b(?:projekt|project)\s+[\"'„“]?{escaped_alias}(?:\b|[\"'“])",
                rf"\bpi\s+(?:im\s+)?(?:projekt\s+)?[\"'„“]?{escaped_alias}(?:\b|[\"'“])",
                rf"\b{escaped_alias}\b",
            )
            if any(re.search(pattern, text) for pattern in patterns):
                matches.append(alias)
        if matches:
            alias = matches[0]
            return alias, projects[alias], None

        default_alias = str(config.get("default_project", "")).strip()
        for alias in projects:
            if alias.casefold() == default_alias.casefold():
                return alias, projects[alias], None

        if len(projects) == 1:
            alias = next(iter(projects))
            return alias, projects[alias], None

        aliases = ", ".join(sorted(projects))
        return None, None, (
            "Bitte nenne das Pi-Projekt. Freigegeben sind: "
            f"{aliases}. Beispiel: „Trinity, nutze Pi im Projekt {sorted(projects)[0]} …“"
        )

    # Pi may also be used as a pure reviewer without project access.
    return "", None, None


def _resolve_executable(raw_executable: str):
    value = os.path.expandvars(os.path.expanduser(str(raw_executable or "pi").strip()))
    if not value:
        value = "pi"
    if os.path.dirname(value):
        path = Path(value)
        return str(path) if path.is_file() else None
    if value.casefold() in {"pi", "pi.exe", "pi.cmd"}:
        return find_pi_executable()
    return shutil.which(value)


def _normalize_arguments(value) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return shlex.split(value)
    return []


def _build_prompt(query: str, alias: str = "", project_path: Path = None) -> str:
    project_line = (
        f"Projekt: {alias}\nArbeitsordner: {project_path}\n\n"
        if alias and project_path
        else ""
    )
    return f"""Du wurdest von Trinity als externer Pi-Hintergrundagent gestartet.

{project_line}
Auftrag des Nutzers:
{query.strip()}

Arbeite im angegebenen Projektordner, falls einer genannt ist. Nutze dort
Projektregeln, vorhandene Agenten, Tests und Dateien. Antworte auf Deutsch.

Sicherheitsregeln fuer diesen fernausgeloesten Lauf:
- Arbeite nur im freigegebenen Projektordner.
- Versende, veroeffentliche oder uebermittle nichts an Dritte.
- Fuehre keine Kaeufe, Loeschungen, Pushes, Deployments oder sonstigen
  irreversiblen externen Aktionen aus.
- Wenn eine solche Aktion noetig waere, bereite sie nur vor und benenne klar,
  was der Nutzer anschliessend selbst bestaetigen muss.
- Berichte am Ende: erledigte Schritte, erzeugte oder geaenderte Dateien,
  Pruefstatus und Blocker.
"""


def _needs_windows_shell(executable: str, host_os=None) -> bool:
    return (host_os or os.name) == "nt" and str(executable).casefold().endswith((".cmd", ".bat"))


def _run_pi(
    executable: str,
    arguments: list[str],
    prompt: str,
    timeout: int,
    project_path: Path = None,
) -> str:
    replaced = False
    command = [executable]
    for argument in arguments:
        if "{prompt}" in argument:
            replaced = True
            command.append(argument.replace("{prompt}", prompt))
        else:
            command.append(argument)

    input_text = None if replaced else prompt
    use_shell = _needs_windows_shell(executable)
    run_command = subprocess.list2cmdline(command) if use_shell else command
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0

    completed = subprocess.run(
        run_command,
        input=input_text,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
        shell=use_shell,
        cwd=str(project_path) if project_path else None,
        env={**os.environ, "NO_COLOR": "1"},
        creationflags=creation_flags,
    )
    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout or "").strip()
        details = _truncate(details, 1200)
        raise OSError(f"Pi wurde mit Fehlercode {completed.returncode} beendet. {details}")
    return completed.stdout


def _result(message: str, alias: str = "") -> dict:
    escaped = html.escape(message)
    subtitle = f"<p>Projekt: {html.escape(alias)}</p>" if alias else ""
    return {
        "direct_answer": message,
        "search_context": "",
        "has_payload": True,
        "html_payload": (
            "<section style='font-family: system-ui; padding: 18px; color: #e5f2ff; "
            "background: #0f172a; border-radius: 14px;'>"
            "<h2 style='margin-top:0;'>Pi</h2>"
            f"{subtitle}"
            f"<pre style='white-space:pre-wrap'>{escaped}</pre>"
            "</section>"
        ),
    }


def _is_project_list_request(query: str) -> bool:
    text = query.casefold()
    return any(
        marker in text
        for marker in (
            "welche pi-projekte",
            "welche pi projekte",
            "pi-projekte",
            "liste pi projekte",
        )
    )


def _project_list_result(projects: dict, default_project: str = "") -> dict:
    if not projects:
        return _result("Für Pi sind noch keine Projektordner freigegeben.")
    lines = ["Freigegebene Pi-Projekte:"]
    for alias, path in sorted(projects.items()):
        suffix = " (Standard)" if alias.casefold() == str(default_project).casefold() else ""
        lines.append(f"- {alias}: {path}{suffix}")
    return _result("\n".join(lines))


def _bounded_int(value, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(number, maximum))


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"

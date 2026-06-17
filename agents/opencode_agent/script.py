"""Bridge from Trinity to the locally installed OpenCode CLI."""

import html
import os
import re
import shutil
import subprocess
from pathlib import Path

import requests
from platform_adapters import find_opencode_executable


PRIORITY = 98

TRIGGERS = (
    "opencode",
    "open code",
    "open-code",
)


def can_handle(query: str) -> bool:
    text = query.casefold()
    return any(trigger in text for trigger in TRIGGERS)


def execute(query: str, context: dict = None) -> dict:
    context = context or {}
    config = dict(context.get("opencode_cfg") or {})

    if not config.get("enabled", False):
        return _result(
            "Der OpenCode-Agent ist noch nicht aktiviert. Öffne Trinitys "
            "Einstellungen und aktiviere ihn im Tab „OpenCode“."
        )

    projects = _configured_projects(config)
    if _is_project_list_request(query):
        return _project_list_result(projects, config.get("default_project", ""))

    alias, project_path, error = _select_project(query, projects, config)
    if error:
        return _result(error)

    executable = _resolve_executable(config.get("executable", "opencode"))
    if not executable:
        return _result(
            "OpenCode wurde auf diesem Rechner nicht gefunden. Installiere die "
            "OpenCode CLI oder trage den vollständigen Pfad in Trinitys "
            "OpenCode-Einstellungen ein."
        )

    _send_telegram_status(
        context,
        f"OpenCode arbeitet jetzt im Projekt „{alias}“. Ich melde mich mit dem Ergebnis.",
    )

    prompt = _build_prompt(query, alias)
    timeout = _bounded_int(config.get("timeout_seconds"), 900, 30, 7200)

    try:
        answer = _run_opencode(
            executable=executable,
            project_path=project_path,
            prompt=prompt,
            timeout=timeout,
            model=str(config.get("model") or "").strip(),
            agent=str(config.get("agent") or "").strip(),
        )
    except subprocess.TimeoutExpired:
        return _result(
            f"OpenCode hat das Zeitlimit von {timeout} Sekunden im Projekt "
            f"„{alias}“ überschritten. Der Lauf wurde beendet.",
            alias,
        )
    except OSError as exc:
        return _result(f"OpenCode konnte nicht gestartet werden: {exc}", alias)

    max_chars = _bounded_int(config.get("max_output_chars"), 3200, 500, 12000)
    answer = _truncate(answer.strip(), max_chars)
    if not answer:
        answer = (
            f"OpenCode hat den Lauf im Projekt „{alias}“ beendet, aber keinen "
            "Abschlussbericht zurückgegeben."
        )

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
    if not projects:
        return None, None, (
            "Für OpenCode ist noch kein Projekt freigegeben. Trage im Tab "
            "„OpenCode“ mindestens einen Projektnamen mit Ordnerpfad ein."
        )

    text = query.casefold()
    matches = []
    for alias in sorted(projects, key=len, reverse=True):
        escaped_alias = re.escape(alias.casefold())
        patterns = (
            rf"\b(?:projekt|project)\s+[\"'„“]?{escaped_alias}(?:\b|[\"'“])",
            rf"\b(?:opencode|open code|open-code)\s+(?:im\s+)?(?:projekt\s+)?[\"'„“]?{escaped_alias}(?:\b|[\"'“])",
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
        "Bitte nenne das OpenCode-Projekt. Freigegeben sind: "
        f"{aliases}. Beispiel: „Trinity, nutze OpenCode im Projekt {sorted(projects)[0]} …“"
    )


def _resolve_executable(raw_executable: str):
    value = os.path.expandvars(os.path.expanduser(str(raw_executable or "opencode").strip()))
    if not value:
        value = "opencode"

    if os.path.dirname(value):
        path = Path(value)
        return str(path) if path.is_file() else None
    if value.casefold() in {"opencode", "opencode.exe", "opencode.cmd"}:
        return find_opencode_executable()
    return shutil.which(value)


def _build_prompt(query: str, alias: str) -> str:
    return f"""Du wurdest von Trinity als lokales OpenCode-Subagententeam gestartet.

Projekt: {alias}
Auftrag des Nutzers:
{query.strip()}

Arbeite den Auftrag im aktuellen Projekt vollständig ab. Nutze vorhandene OpenCode-
Agenten, Projektregeln, Automationspipelines und lokale Werkzeuge, wenn sie zum
Auftrag gehören.

Sicherheitsregeln für diesen fernausgelösten Lauf:
- Versende, veröffentliche oder übermittle nichts an Dritte.
- Erstelle E-Mails und Nachrichten ausschließlich als Entwurf.
- Führe keine Käufe, Löschungen, Pushes, Deployments oder sonstigen irreversiblen
  externen Aktionen aus.
- Wenn eine solche Aktion nötig wäre, bereite sie nur vor und benenne klar, was der
  Nutzer anschließend selbst bestätigen muss.

Antworte am Ende auf Deutsch mit einem knappen Bericht: erledigte Schritte, erzeugte
Entwürfe oder Dateien, Prüfstatus und gegebenenfalls ein konkreter Blocker.
"""


def _needs_windows_shell(executable: str, host_os=None) -> bool:
    return (host_os or os.name) == "nt" and str(executable).casefold().endswith((".cmd", ".bat"))


def _run_opencode(
    executable: str,
    project_path: Path,
    prompt: str,
    timeout: int,
    model: str = "",
    agent: str = "",
) -> str:
    command = [executable, "run"]
    if model:
        command.extend(["--model", model])
    if agent:
        command.extend(["--agent", agent])
    command.append(prompt)

    creation_flags = 0
    if os.name == "nt":
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    use_shell = _needs_windows_shell(executable)
    run_command = subprocess.list2cmdline(command) if use_shell else command
    completed = subprocess.run(
        run_command,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
        shell=use_shell,
        cwd=str(project_path),
        env={**os.environ, "NO_COLOR": "1"},
        creationflags=creation_flags,
    )

    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout or "").strip()
        details = _truncate(details, 1200)
        raise OSError(
            f"OpenCode wurde mit Fehlercode {completed.returncode} beendet. {details}"
        )
    return completed.stdout


def _send_telegram_status(context: dict, message: str) -> None:
    if not context.get("from_telegram"):
        return
    telegram = context.get("telegram_cfg") or {}
    token = telegram.get("bot_token")
    chat_id = telegram.get("chat_id")
    if not token or not chat_id:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message},
            timeout=5,
        )
    except requests.RequestException as exc:
        print(f"Telegram-Status für OpenCode konnte nicht gesendet werden: {exc}")


def _is_project_list_request(query: str) -> bool:
    text = query.casefold()
    return any(
        phrase in text
        for phrase in (
            "opencode projekte",
            "opencode-projekte",
            "open code projekte",
            "welche opencode projekte",
            "liste die opencode projekte",
            "zeige die opencode projekte",
        )
    )


def _project_list_result(projects: dict, default_alias: str) -> dict:
    if not projects:
        return _result("Für OpenCode sind noch keine Projekte freigegeben.")
    labels = []
    for alias in sorted(projects):
        suffix = " (Standard)" if alias == default_alias else ""
        labels.append(f"{alias}{suffix}")
    return _result("Freigegebene OpenCode-Projekte: " + ", ".join(labels))


def _result(message: str, project_alias: str = "") -> dict:
    title = "OpenCode"
    if project_alias:
        title += f" · {project_alias}"
    payload = f"""
    <!-- KEEP_OPEN -->
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                max-width:760px;margin:20px auto;line-height:1.5;">
      <h2 style="margin:0 0 14px;font-size:20px;">{html.escape(title)}</h2>
      <div style="white-space:pre-wrap;">{html.escape(message)}</div>
    </div>
    """
    return {
        "has_payload": True,
        "html_payload": payload,
        "search_context": "",
        "direct_answer": message,
    }


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 80)].rstrip() + (
        "\n\n[Abschlussbericht für Trinity gekürzt. Details liegen im Projekt.]"
    )


def _bounded_int(value, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))

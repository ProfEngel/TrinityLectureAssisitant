"""Bridge from Trinity to the locally installed Codex CLI."""

import html
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import requests
from platform_adapters import find_codex_executable


REQUIRED_CAPABILITIES = {"codex_cli"}
PRIORITY = 100

TRIGGERS = (
    "codex",
    "kodeks",
    "code x",
)


def can_handle(query: str) -> bool:
    text = query.casefold()
    return any(trigger in text for trigger in TRIGGERS)


def execute(query: str, context: dict = None) -> dict:
    context = context or {}
    config = dict(context.get("codex_cfg") or {})

    if not config.get("enabled", False):
        return _result(
            "Der Codex-Agent ist noch nicht aktiviert. Öffne Trinitys Einstellungen "
            "und aktiviere ihn im Tab „Codex“."
        )

    projects = _configured_projects(config)
    if _is_project_list_request(query):
        return _project_list_result(projects, config.get("default_project", ""))

    alias, project_path, error = _select_project(query, projects, config)
    if error:
        return _result(error)

    executable = _resolve_executable(config.get("executable", "codex"))
    if not executable:
        return _result(
            "Codex wurde auf diesem Rechner nicht gefunden. Installiere die Codex CLI "
            "und prüfe anschließend den Programmpfad in Trinitys Codex-Einstellungen."
        )

    _send_telegram_status(
        context,
        f"Codex arbeitet jetzt im Projekt „{alias}“. Ich melde mich mit dem Ergebnis.",
    )

    prompt = _build_prompt(query, alias)
    timeout = _bounded_int(config.get("timeout_seconds"), 900, 30, 3600)
    sandbox = config.get("sandbox", "workspace-write")
    if sandbox not in {"read-only", "workspace-write"}:
        sandbox = "workspace-write"

    try:
        answer = _run_codex(
            executable=executable,
            project_path=project_path,
            prompt=prompt,
            sandbox=sandbox,
            timeout=timeout,
            ephemeral=bool(config.get("ephemeral", True)),
            network_access=bool(config.get("network_access", False)),
        )
    except subprocess.TimeoutExpired:
        return _result(
            f"Codex hat das Zeitlimit von {timeout} Sekunden im Projekt „{alias}“ "
            "überschritten. Der Lauf wurde beendet.",
            alias,
        )
    except OSError as exc:
        return _result(f"Codex konnte nicht gestartet werden: {exc}", alias)

    max_chars = _bounded_int(config.get("max_output_chars"), 3200, 500, 12000)
    answer = _truncate(answer.strip(), max_chars)
    if not answer:
        answer = (
            f"Codex hat den Lauf im Projekt „{alias}“ beendet, aber keinen "
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
            "Für Codex ist noch kein Projekt freigegeben. Trage im Tab „Codex“ "
            "mindestens einen Projektnamen mit Ordnerpfad ein."
        )

    text = query.casefold()
    matches = []
    for alias in sorted(projects, key=len, reverse=True):
        escaped_alias = re.escape(alias.casefold())
        patterns = (
            rf"\b(?:projekt|project)\s+[\"'„“]?{escaped_alias}(?:\b|[\"'“])",
            rf"\bcodex\s+(?:im\s+)?(?:projekt\s+)?[\"'„“]?{escaped_alias}(?:\b|[\"'“])",
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
        "Bitte nenne das Codex-Projekt. Freigegeben sind: "
        f"{aliases}. Beispiel: „Trinity, nutze Codex im Projekt {sorted(projects)[0]} …“"
    )


def _resolve_executable(raw_executable: str):
    value = os.path.expandvars(os.path.expanduser(str(raw_executable or "codex").strip()))
    if not value:
        value = "codex"

    if os.path.dirname(value):
        path = Path(value)
        return str(path) if path.is_file() else None
    if value.casefold() in {"codex", "codex.exe", "codex.cmd"}:
        return find_codex_executable()
    return shutil.which(value)


def _build_prompt(query: str, alias: str) -> str:
    return f"""Du wurdest von Trinity als lokaler Ausführungsagent gestartet.

Projekt: {alias}
Auftrag des Nutzers:
{query.strip()}

Arbeite den Auftrag im aktuellen Projekt vollständig ab. Nutze passende installierte
Codex-Skills und, wenn ausdrücklich verlangt oder im Projekt vorgesehen, Subagenten.
Beachte alle AGENTS.md- und Projektregeln. Prüfe dein Ergebnis, bevor du abschließt.

Sicherheitsregeln für diesen fernausgelösten Lauf:
- Wenn das Projekt ein BrainVault-Agentenpool ist (`.agents` und `AGENTS.md`
  vorhanden), darfst Du dort Agenten lesen, anlegen, überarbeiten, testen,
  katalogisieren und passende Reports ablegen, soweit der Nutzer das beauftragt.
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


def _run_codex(
    executable: str,
    project_path: Path,
    prompt: str,
    sandbox: str,
    timeout: int,
    ephemeral: bool,
    network_access: bool,
) -> str:
    with tempfile.TemporaryDirectory(prefix="trinity-codex-") as temp_dir:
        output_path = Path(temp_dir) / "last-message.txt"
        command = [
            executable,
            "exec",
            "--cd",
            str(project_path),
            "--sandbox",
            sandbox,
            "--color",
            "never",
            "--skip-git-repo-check",
            "--output-last-message",
            str(output_path),
            "-c",
            'approval_policy="never"',
        ]
        if sandbox == "workspace-write":
            command.extend(
                ["-c", "sandbox_workspace_write.writable_roots=[]"]
            )
            command.extend(
                [
                    "-c",
                    "sandbox_workspace_write.network_access="
                    + ("true" if network_access else "false"),
                ]
            )
        if ephemeral:
            command.append("--ephemeral")
        command.append("-")

        creation_flags = 0
        if os.name == "nt":
            creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        use_shell = _needs_windows_shell(executable)
        run_command = subprocess.list2cmdline(command) if use_shell else command
        completed = subprocess.run(
            run_command,
            input=prompt,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
            # Windows may route npm-installed .cmd launchers through cmd.exe.
            # Enabling shell handling for that known executable lets Python apply
            # the required argument escaping; the user prompt remains on stdin.
            shell=use_shell,
            cwd=str(project_path),
            env={**os.environ, "NO_COLOR": "1"},
            creationflags=creation_flags,
        )

        if output_path.exists():
            final_message = output_path.read_text(encoding="utf-8", errors="replace")
        else:
            final_message = completed.stdout

        if completed.returncode != 0:
            details = (completed.stderr or completed.stdout or "").strip()
            details = _truncate(details, 1200)
            raise OSError(
                f"Codex wurde mit Fehlercode {completed.returncode} beendet. {details}"
            )
        return final_message


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
        print(f"Telegram-Status für Codex konnte nicht gesendet werden: {exc}")


def _is_project_list_request(query: str) -> bool:
    text = query.casefold()
    return any(
        phrase in text
        for phrase in (
            "codex projekte",
            "codex-projekte",
            "welche projekte",
            "liste die projekte",
            "zeige die projekte",
        )
    )


def _project_list_result(projects: dict, default_alias: str) -> dict:
    if not projects:
        return _result("Für Codex sind noch keine Projekte freigegeben.")
    labels = []
    for alias in sorted(projects):
        suffix = " (Standard)" if alias == default_alias else ""
        labels.append(f"{alias}{suffix}")
    return _result("Freigegebene Codex-Projekte: " + ", ".join(labels))


def _result(message: str, project_alias: str = "") -> dict:
    title = "Codex"
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
        "\n\n[Abschlussbericht für Telegram gekürzt. Details liegen im Projekt.]"
    )


def _bounded_int(value, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))

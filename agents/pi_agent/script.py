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

    timeout = _bounded_int(config.get("timeout_seconds"), 600, 30, 3600)
    arguments = _normalize_arguments(config.get("arguments", []))
    prompt = _build_prompt(query)

    try:
        answer = _run_pi(
            executable=executable,
            arguments=arguments,
            prompt=prompt,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return _result(f"Pi hat das Zeitlimit von {timeout} Sekunden überschritten.")
    except OSError as exc:
        return _result(f"Pi konnte nicht gestartet werden: {exc}")

    max_chars = _bounded_int(config.get("max_output_chars"), 3200, 500, 12000)
    answer = _truncate(answer.strip(), max_chars)
    if not answer:
        answer = "Pi hat den Lauf beendet, aber keine Antwort zurückgegeben."
    return _result(answer)


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


def _build_prompt(query: str) -> str:
    return f"""Du wurdest von Trinity als externer Pi-Hintergrundagent gestartet.

Auftrag des Nutzers:
{query.strip()}

Antworte auf Deutsch. Fuehre keine irreversiblen externen Aktionen aus.
Wenn Du etwas nur vorbereiten kannst, benenne klar, was der Nutzer selbst
bestaetigen muss.
"""


def _needs_windows_shell(executable: str, host_os=None) -> bool:
    return (host_os or os.name) == "nt" and str(executable).casefold().endswith((".cmd", ".bat"))


def _run_pi(executable: str, arguments: list[str], prompt: str, timeout: int) -> str:
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
        env={**os.environ, "NO_COLOR": "1"},
        creationflags=creation_flags,
    )
    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout or "").strip()
        details = _truncate(details, 1200)
        raise OSError(f"Pi wurde mit Fehlercode {completed.returncode} beendet. {details}")
    return completed.stdout


def _result(message: str) -> dict:
    escaped = html.escape(message)
    return {
        "direct_answer": message,
        "search_context": "",
        "has_payload": True,
        "html_payload": (
            "<section style='font-family: system-ui; padding: 18px; color: #e5f2ff; "
            "background: #0f172a; border-radius: 14px;'>"
            "<h2 style='margin-top:0;'>Pi</h2>"
            f"<pre style='white-space:pre-wrap'>{escaped}</pre>"
            "</section>"
        ),
    }


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

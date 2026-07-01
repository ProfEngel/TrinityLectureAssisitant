"""Generic bridge from Trinity to a user-provided Pi CLI wrapper."""

from __future__ import annotations

import html
import json
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path

try:
    from brainvault_agents import brainvault_root_from_config
except Exception:  # pragma: no cover - optional during isolated script use
    brainvault_root_from_config = None

from platform_adapters import find_pi_executable


PRIORITY = 97

TRIGGER_PATTERNS = (
    r"\b(?:nutze|starte|frage|frag|verwende)\s+pi\b",
    r"\bpi\s+(?:nach|zu|ueber|über)\b",
    r"\bpi[- ]agent\b",
    r"\bpi[- ]cli\b",
)

CAPABILITY_PATTERNS = (
    r"\bwelche\s+(?:faehigkeiten|fähigkeiten|skills|agenten)\b",
    r"\bwas\s+kannst\s+du\b",
    r"\bwas\s+kann\s+trinity\b",
    r"\bzeig(?:e)?\s+(?:mir\s+)?(?:deine\s+)?(?:faehigkeiten|fähigkeiten|skills|agenten)\b",
)

AGENT_POOL_PATTERNS = (
    r"\bbrainvault\b",
    r"\bbrainvault[- ]?agent",
    r"\bagentenpool\b",
    r"\bcloud[- ]?agent",
    r"\bexterne(?:n|r|s)?\s+agent",
    r"\bnutze\s+(?:den|die|das)?\s*.+agent",
    r"\bstarte\s+(?:den|die|das)?\s*.+agent",
    r"\bmail[- ]?agent",
    r"\bmail(?:rundlauf|entwurf|entwuerf|entwürf|triage)\b",
    r"\bgutachten(?:agent)?\b",
    r"\bbewertung(?:sagent)?\b",
    r"\bhtml[- ]?praesentation|\bhtml[- ]?präsentation",
    r"\berendria\b",
)


def can_handle(query: str) -> bool:
    text = query.casefold()
    return any(
        re.search(pattern, text)
        for pattern in (*TRIGGER_PATTERNS, *CAPABILITY_PATTERNS, *AGENT_POOL_PATTERNS)
    )


def execute(query: str, context: dict = None) -> dict:
    context = context or {}
    config = dict(context.get("pi_cfg") or {})
    projects = _configured_projects(config)

    if _is_capability_request(query) and not _is_explicit_pi_request(query):
        return _capability_result(query, context, projects, config)

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
            project_alias=alias,
        )
    except subprocess.TimeoutExpired:
        return _result(f"Pi hat das Zeitlimit von {timeout} Sekunden überschritten.")
    except OSError as exc:
        return _result(f"Pi konnte nicht gestartet werden: {exc}")

    max_chars = _bounded_int(config.get("max_output_chars"), 3200, 500, 12000)
    answer = _truncate(_clean_pi_answer(answer).strip(), max_chars)
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
    brainvault_context = _brainvault_query_context(project_path, query)
    project_line = (
        f"Projekt: {alias}\nArbeitsordner: {project_path}\n"
        "Du wurdest bereits mit diesem Arbeitsordner als current working "
        "directory gestartet.\n\n"
        if alias and project_path
        else ""
    )
    return f"""Du wurdest von Trinity als externer Pi-Hintergrundagent gestartet.

{project_line}
{brainvault_context}
Auftrag des Nutzers:
{query.strip()}

Arbeite im angegebenen Projektordner, falls einer genannt ist. Nutze dort
Projektregeln, vorhandene Agenten, Tests und Dateien. Antworte auf Deutsch.

Wichtig fuer Dateizugriff:
- Nutze bevorzugt relative Pfade ab dem Arbeitsordner, z.B. `AGENTS.md`,
  `.agents/mail/...` oder `.catalog/...`.
- Vermeide absolute iCloud-/OneDrive-Pfade mit Leerzeichen in internen
  Read-Tools. Wenn ein Tool absolute Pfade falsch quotet, lies Dateien per
  Shell aus dem aktuellen Arbeitsordner, z.B. `pwd`, `ls -la`, `find .agents
  -maxdepth 3 -name agent.yaml`, `sed -n '1,160p' AGENTS.md` oder `python3`.
- Wenn Du einen absoluten Pfad brauchst, quote ihn nur im Shell-Kommando selbst
  und baue ihn nicht in ein internes Read-Tool ein.

Sicherheitsregeln fuer diesen fernausgeloesten Lauf:
- Arbeite nur im freigegebenen Projektordner.
- Wenn der freigegebene Projektordner ein BrainVault-Agentenpool ist
  (`.agents` und `AGENTS.md` vorhanden), darfst Du dort Agenten lesen, anlegen,
  ueberarbeiten, testen, katalogisieren und passende Reports ablegen, soweit der
  Nutzer das beauftragt.
- Mail-Auftraege: Du darfst lokale Mail-Agenten, Apple-Mail-Automationen oder
  Skripte nutzen, wenn der Nutzer es ausdruecklich beauftragt. Standard ist:
  Antworten als Entwurf vorbereiten und transparent berichten. Senden, Loeschen
  oder Verschieben von Mails ist nur erlaubt, wenn der Nutzer diese konkrete
  Aktion ausdruecklich freigibt.
- Fuer Import-Auftraege darfst Du explizit vom Nutzer genannte Quellpfade
  read-only analysieren. Schreibe, kopiere oder normalisiere Ergebnisse aber
  nur in den freigegebenen Projektordner.
- Versende, veroeffentliche oder uebermittle nichts an Dritte.
- Fuehre keine Kaeufe, Loeschungen, Pushes, Deployments oder sonstigen
  irreversiblen externen Aktionen aus.
- Wenn eine solche Aktion noetig waere, bereite sie nur vor und benenne klar,
  was der Nutzer anschliessend selbst bestaetigen muss.
- Berichte am Ende: erledigte Schritte, erzeugte oder geaenderte Dateien,
  Pruefstatus und Blocker.
"""


def _brainvault_query_context(project_path: Path = None, query: str = "") -> str:
    if not project_path or not (project_path / ".agents").is_dir():
        return ""
    terms = _query_terms(query)
    if not terms:
        return ""

    lines = []
    agent_hits = _matching_brainvault_agents(project_path, terms)
    project_hits = _matching_brainvault_projects(project_path, terms)
    if agent_hits:
        lines.append("Vorab aus Trinitys BrainVault-Agentenindex gefundene Treffer:")
        lines.extend(f"- {item}" for item in agent_hits[:8])
    if project_hits:
        if not lines:
            lines.append("Vorab aus Trinitys BrainVault-Projektindex gefundene Treffer:")
        else:
            lines.append("Passende BrainVault-Projektordner:")
        lines.extend(f"- {item}" for item in project_hits[:8])
    if not lines:
        return ""
    lines.append(
        "Nutze diese Treffer aktiv als Startpunkt und pruefe bei Bedarf die "
        "genannten Dateien relativ zum Arbeitsordner."
    )
    return "\n".join(lines) + "\n\n"


def _query_terms(query: str) -> list[str]:
    stopwords = {
        "trinity",
        "bitte",
        "frage",
        "frag",
        "nach",
        "dazu",
        "darum",
        "welche",
        "agenten",
        "projekt",
        "projekte",
        "brainvault",
        "nutze",
        "zeige",
        "hier",
        "dann",
        "alle",
        "ordner",
    }
    result = []
    for raw in re.findall(r"[A-Za-zÄÖÜäöüß0-9_-]{4,}", str(query or "").casefold()):
        term = raw.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
        if term in stopwords or term in result:
            continue
        result.append(term)
    return result[:8]


def _matching_brainvault_agents(root: Path, terms: list[str]) -> list[str]:
    hits = []
    agents_dir = root / ".agents"
    for agent_yaml in sorted(agents_dir.rglob("agent.yaml")):
        try:
            raw = agent_yaml.read_text(encoding="utf-8", errors="ignore")[:12000]
        except OSError:
            continue
        haystack = _normalize_for_search(f"{agent_yaml.relative_to(root).as_posix()}\n{raw}")
        if not any(term in haystack for term in terms):
            continue
        name = _yaml_scalar(raw, "name") or agent_yaml.parent.name
        agent_id = _yaml_scalar(raw, "id") or agent_yaml.parent.name
        status = _yaml_scalar(raw, "status") or "unbekannt"
        preferred = _yaml_scalar(raw, "preferred_harness") or "auto"
        workspace = _yaml_scalar(raw, "workspace")
        description = _yaml_scalar(raw, "description")
        relative = agent_yaml.parent.relative_to(root).as_posix()
        item = f"{name} ({agent_id}, {status}, Harness: {preferred}) unter {relative}"
        if workspace and workspace.casefold() not in {"null", "none"}:
            item += f"; Workspace: {workspace}"
        if description:
            item += f"; Zweck: {_truncate(description, 180)}"
        hits.append(item)
    return hits


def _matching_brainvault_projects(root: Path, terms: list[str]) -> list[str]:
    hits = []
    for relative_base in (
        Path("Ideaverse") / "projects",
        Path("CampusHub") / "projects",
        Path("MainHub"),
    ):
        base = root / relative_base
        if not base.is_dir():
            continue
        for child in sorted(base.iterdir()):
            if not child.is_dir():
                continue
            haystack = _normalize_for_search(child.name)
            if any(term in haystack for term in terms):
                hits.append(child.relative_to(root).as_posix())
    return hits


def _yaml_scalar(raw: str, key: str) -> str:
    match = re.search(rf"(?m)^{re.escape(key)}:\s*(.+?)\s*$", raw)
    if not match:
        return ""
    value = match.group(1).strip()
    if value in {"|", ">"}:
        return ""
    return value.strip("\"'")


def _normalize_for_search(value: str) -> str:
    text = str(value or "").casefold()
    return text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")


def _clean_pi_answer(answer: str) -> str:
    text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", str(answer or "")).strip()
    if not text:
        return ""
    if text[:300].casefold().startswith("here's a thinking process"):
        markers = (
            "\nTrinity:",
            "\nAntwort:",
            "\nFinal Answer:",
            "\nFinal:",
        )
        for marker in markers:
            if marker in text:
                return text.rsplit(marker, 1)[-1].strip()
        quoted = [
            item.strip()
            for item in re.findall(r'"([^"]{40,})"', text, flags=re.DOTALL)
            if item.strip()
        ]
        if quoted:
            return quoted[-1]
    return text


def _needs_windows_shell(executable: str, host_os=None) -> bool:
    return (host_os or os.name) == "nt" and str(executable).casefold().endswith((".cmd", ".bat"))


def _subprocess_env(executable: str, project_path: Path = None, project_alias: str = "") -> dict:
    path_entries = []
    executable_dir = os.path.dirname(str(executable or ""))
    if executable_dir:
        path_entries.append(executable_dir)
    path_entries.extend(
        [
            "/opt/homebrew/bin",
            "/opt/homebrew/sbin",
            "/usr/local/bin",
            "/usr/local/sbin",
            "/usr/bin",
            "/bin",
            "/usr/sbin",
            "/sbin",
        ]
    )
    path_entries.extend(os.environ.get("PATH", "").split(os.pathsep))

    clean_path = []
    seen = set()
    for entry in path_entries:
        if entry and entry not in seen:
            seen.add(entry)
            clean_path.append(entry)

    env = {
        **os.environ,
        "NO_COLOR": "1",
        "PATH": os.pathsep.join(clean_path),
        "TRINITY_PROJECT_ALIAS": str(project_alias or ""),
    }
    if project_path:
        env["TRINITY_PROJECT_ROOT"] = str(project_path)
        if (project_path / ".agents").is_dir():
            env["TRINITY_BRAINVAULT_ROOT"] = str(project_path)
    return env


def _run_pi(
    executable: str,
    arguments: list[str],
    prompt: str,
    timeout: int,
    project_path: Path = None,
    project_alias: str = "",
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
    env = _subprocess_env(executable, project_path, project_alias)

    completed = subprocess.run(
        run_command,
        input=input_text,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
        shell=use_shell,
        cwd=str(project_path) if project_path else None,
        env=env,
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


def _is_capability_request(query: str) -> bool:
    text = query.casefold()
    return any(re.search(pattern, text) for pattern in CAPABILITY_PATTERNS)


def _is_explicit_pi_request(query: str) -> bool:
    text = query.casefold()
    return any(re.search(pattern, text) for pattern in TRIGGER_PATTERNS)


def _capability_result(query: str, context: dict, projects: dict, config: dict) -> dict:
    brainvault_alias, brainvault_path = _default_project(projects, config)
    if not brainvault_path:
        brainvault_alias, brainvault_path = _project_from_control_plane(context)
    external_agents = _load_brainvault_agent_summary(brainvault_path) if brainvault_path else []
    local_items = _local_capabilities(context)
    default_harness = _default_harness_label(context)
    builder = _builder_harness_label(context)

    lines = [
        "Ich habe zwei Fähigkeitsebenen:",
        "",
        "1. Trinity direkt",
    ]
    for item in local_items:
        lines.append(f"- {item}")

    lines.extend(
        [
            "",
            f"2. Erweiterungen aus dem BrainVault-Agentenpool ({default_harness} als Standard-Harness)",
        ]
    )
    if brainvault_path:
        lines.append(f"- Agentenpool: {brainvault_alias or 'BrainVault'}")
        if external_agents:
            for agent in external_agents[:12]:
                suffix = f" ({agent['status']})" if agent.get("status") and agent.get("status") != "active" else ""
                lines.append(f"- {agent['name']}{suffix}: {agent['description']}")
            if len(external_agents) > 12:
                lines.append(f"- ... plus {len(external_agents) - 12} weitere katalogisierte Agenten.")
        else:
            lines.append("- Noch keine aktiven externen Agenten im Katalog gefunden.")
    else:
        lines.append("- Noch kein BrainVault-Projekt fuer Pi freigegeben.")

    lines.extend(
        [
            "",
            "Wichtig:",
            f"- Normale bestehende BrainVault-Agentenarbeit laeuft automatisch ueber {default_harness}.",
            f"- Neue Agenten, Imports, Refactorings und Quality-Gates gehen ueber {builder}.",
            "- Du musst Pi nicht nennen. Sag einfach, was passieren soll.",
            "- Codex und Antigravity duerfen denselben BrainVault-Agentenpool weiterhin direkt nutzen; die Regeln beschraenken den Pool nicht auf Pi.",
            "",
            "Beispiele:",
            "- Trinity, welche Faehigkeiten hast Du?",
            "- Trinity, gibt es einen Mail-Agenten und was kann der?",
            "- Trinity, erstelle mir Mailentwuerfe fuer die heutigen Rueckfragen.",
            "- Trinity, welche Review- oder Bewertungsagenten gibt es?",
            "- Trinity, baue einen neuen Agenten fuer Steuerdaten.  (Dann nimmt Trinity den Builder-Harness.)",
        ]
    )
    return _result("\n".join(lines), brainvault_alias)


def _default_project(projects: dict, config: dict):
    if not projects:
        return "", None
    default_alias = str(config.get("default_project", "")).strip()
    for alias, path in projects.items():
        if alias.casefold() == default_alias.casefold():
            return alias, path
    for alias, path in projects.items():
        if alias.casefold() == "brainvault":
            return alias, path
    if len(projects) == 1:
        return next(iter(projects.items()))
    return "", None


def _project_from_control_plane(context: dict):
    brain = (context or {}).get("brain")
    config = getattr(brain, "config", {}) if brain is not None else {}
    if not isinstance(config, dict):
        return "", None
    if brainvault_root_from_config is not None:
        try:
            repo_root = Path(__file__).resolve().parents[2]
            path = brainvault_root_from_config(repo_root, config)
            if path.is_dir() and (path / ".agents").is_dir():
                return "BrainVault", path
        except Exception:
            pass
    control = config.get("control_plane") or {}
    for key in ("external_agents_root", "brainvault_root", "vault_root"):
        raw_path = str(control.get(key) or "").strip()
        if not raw_path:
            continue
        path = Path(os.path.expandvars(os.path.expanduser(raw_path))).resolve()
        if path.is_dir() and (path / ".agents").is_dir():
            return "BrainVault", path
    return "", None


def _load_brainvault_agent_summary(root: Path) -> list[dict]:
    if not root:
        return []
    catalog = root / ".agents" / "_meta" / "agent_catalog.json"
    if not catalog.is_file():
        catalog = root / ".catalog" / "agent_catalog.json"
    try:
        data = json.loads(catalog.read_text(encoding="utf-8"))
    except Exception:
        return []
    agents = data.get("agents") if isinstance(data, dict) else []
    if not isinstance(agents, list):
        return []

    result = []
    for agent in agents:
        if not isinstance(agent, dict) or not agent.get("enabled", True):
            continue
        status = str(agent.get("status") or "").strip()
        if status not in {"", "active", "validated", "stable", "testing"}:
            continue
        name = str(agent.get("name") or agent.get("id") or "Agent").strip()
        if name.startswith("---"):
            continue
        if name.startswith("/") and " - " in name:
            name = name.split(" - ", 1)[1].strip()
        description = str(agent.get("description") or "").strip()
        if description in {"$ARGUMENTS", ""}:
            description = "katalogisierte BrainVault-Faehigkeit"
        if len(description) > 120:
            description = description[:117].rstrip() + "..."
        result.append(
            {
                "name": name,
                "description": description or "katalogisierte BrainVault-Faehigkeit",
                "status": status or "active",
            }
        )
    def sort_key(item: dict):
        text = f"{item['name']} {item['description']}".casefold()
        priority = 5
        for index, marker in enumerate(("mail", "gutachten", "bewertung", "praesentation", "präsentation", "research")):
            if marker in text:
                priority = index
                break
        return (priority, item["name"].casefold())

    return sorted(result, key=sort_key)


def _local_capabilities(context: dict) -> list[str]:
    default_items = [
        "Zuhoeren per STT, Chat/Fluestern, iPad/iPhone-Companion und Desktop-UI.",
        "Vortrag/Web/Alltag/Chat mit Mitschrift, Medien-Overlays und Payload-Verlauf.",
        "Dokumente, PDFs, Bilder, Memory, RAG und lokale Agenten wie Recherche, Sandbox, Simulation oder ComfyUI-Medien.",
    ]
    brain = (context or {}).get("brain")
    skills = getattr(brain, "live_skills", []) if brain is not None else []
    names = []
    for skill in skills:
        module_name = str(getattr(skill, "__name__", "")).split(".")[-1]
        if not module_name or module_name in {"pi_agent", "codex_agent", "opencode_agent"}:
            continue
        clean = module_name.replace("_agent", "").replace("_", " ").strip()
        if clean and clean not in names:
            names.append(clean)
    if names:
        default_items.append("Aktive lokale Skills: " + ", ".join(names[:12]) + ".")
    return default_items


def _default_harness_label(context: dict) -> str:
    config = getattr((context or {}).get("brain"), "config", {}) if (context or {}).get("brain") else {}
    control = config.get("control_plane", {}) if isinstance(config, dict) else {}
    return str(control.get("default_brainvault_harness") or "pi")


def _builder_harness_label(context: dict) -> str:
    config = getattr((context or {}).get("brain"), "config", {}) if (context or {}).get("brain") else {}
    control = config.get("control_plane", {}) if isinstance(config, dict) else {}
    return str(control.get("builder_harness") or "codex")


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

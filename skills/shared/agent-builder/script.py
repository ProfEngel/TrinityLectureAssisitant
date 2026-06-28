"""Shared Agentenbuilder skill for Trinity's controlled agent forge."""

import html
import json
import re
import shutil
import time
from pathlib import Path
from typing import Optional


PRIORITY = 99

TRIGGER_PATTERNS = (
    r"\bagentenbuilder\b",
    r"\bagent builder\b",
    r"\b(?:baue|erstelle|entwickle)\s+(?:einen\s+)?agenten\b",
    r"\b(?:importiere|importier|uebernimm|übernimm|hol(?:e)?\s+dir)\s+(?:diesen\s+|den\s+|einen\s+)?agenten\b",
    r"\bagenten?\s+(?:aendern|ändern|erweitern|verbessern|umbauen)\b",
    r"\b(?:aendere|ändere|erweitere|verbessere)\s+(?:den\s+|einen\s+)?agenten\b",
    r"\bneuen\s+agenten\b",
)

IMPORT_PATTERNS = (
    "importiere",
    "importier",
    "uebernimm",
    "übernimm",
    "hol dir",
    "hole dir",
    "vorhandenen agent",
)
EDIT_PATTERNS = ("aendere", "ändere", "erweitere", "verbessere", "umbauen")
RELEVANT_SUFFIXES = {
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".py",
    ".toml",
    ".ini",
    ".cfg",
}
MAX_SNAPSHOT_BYTES = 2 * 1024 * 1024
MAX_SNAPSHOT_FILES = 80


def can_handle(query: str) -> bool:
    text = str(query or "").casefold()
    return any(re.search(pattern, text) for pattern in TRIGGER_PATTERNS)


def execute(query: str, context=None) -> dict:
    context = context or {}
    decision = context.get("task_decision")
    job = getattr(decision, "job", None) if decision is not None else None
    job_id = (job or {}).get("job_id", "")
    route = getattr(decision, "route", "agent_forge") if decision is not None else "agent_forge"
    title = _short_title(query)
    action = _classify_action(query)

    import_result = None
    if action == "import":
        source_path = _source_path_from_context(query, context)
        if source_path and source_path.exists():
            import_result = _stage_agent_import(source_path, query, job_id)
        else:
            import_result = {
                "ok": False,
                "message": (
                    "Ich brauche fuer den Import einen lokalen Agentenordner "
                    "oder eine Agenten-Uebersichtsdatei als Anlage oder als "
                    "vollstaendigen, am besten in Anfuehrungszeichen gesetzten Pfad."
                ),
                "source_path": str(source_path) if source_path else "",
                "staging_path": "",
                "skill_id": "",
                "subagents": [],
            }

    message = _direct_message(action, import_result)
    if job_id:
        message += f" Der Builder-Auftrag laeuft unter Job {job_id}."

    html_payload = _html_payload(
        title=title,
        query=query,
        job_id=job_id,
        route=route,
        action=action,
        import_result=import_result,
    )
    return {
        "direct_answer": message,
        "has_payload": True,
        "html_payload": html_payload,
        "search_context": "",
    }


def _short_title(query: str) -> str:
    compact = " ".join(str(query or "").split())
    if not compact:
        return "Neuer Trinity-Agent"
    return compact[:90]


def _classify_action(query: str) -> str:
    text = str(query or "").casefold()
    if any(pattern in text for pattern in IMPORT_PATTERNS):
        return "import"
    if any(pattern in text for pattern in EDIT_PATTERNS):
        return "edit"
    return "create"


def _direct_message(action: str, import_result) -> str:
    if action == "import" and import_result:
        if import_result.get("ok"):
            return (
                "Ich habe den Agentenimport als Staging-Skill vorbereitet. "
                f"Skill-ID: {import_result['skill_id']}. "
                "Bitte pruefe Importbericht, Tests und Freigabe, bevor der Agent "
                "produktiver Personal- oder Shared-Agent wird."
            )
        return "Ich habe den Agentenimport vorbereitet, brauche aber noch eine eindeutige Quelle."
    if action == "edit":
        return (
            "Ich habe den Agentenbuilder fuer eine Aenderung oder Erweiterung aktiviert. "
            "Der sichere Weg ist: bestehenden Agenten identifizieren, Zielverhalten "
            "beschreiben, Tests ergaenzen, Staging-Aenderung bauen und erst nach "
            "Freigabe produktiv ersetzen."
        )
    return (
        "Ich habe den Agentenbuilder aktiviert. "
        "Der naechste sichere Schritt ist: Anforderungen klaeren, Plan erstellen, "
        "Staging-Agent bauen, Tests/Quality-Gates laufen lassen und erst nach Deiner "
        "Freigabe produktiv registrieren."
    )


def _html_payload(title: str, query: str, job_id: str, route: str, action: str, import_result=None) -> str:
    rows = _plan_rows(action, import_result)
    items = "".join(
        "<li><strong>{step}. {name}</strong><br><span>{desc}</span></li>".format(
            step=html.escape(step),
            name=html.escape(name),
            desc=html.escape(desc),
        )
        for step, name, desc in rows
    )
    job_line = (
        f"<p><strong>Job:</strong> {html.escape(job_id)} · Route: {html.escape(route)}</p>"
        if job_id
        else "<p><strong>Job:</strong> noch kein persistenter Job uebergeben.</p>"
    )
    import_block = _import_block(import_result)
    return (
        "<section style='font-family: system-ui; padding: 20px; color: #e8f3ff; "
        "background: linear-gradient(135deg,#111827,#172554); border-radius: 16px;'>"
        "<h2 style='margin-top:0;'>Trinity Agentenbuilder</h2>"
        f"<p><strong>Auftrag:</strong> {html.escape(title)}</p>"
        f"<p><strong>Modus:</strong> {html.escape(action)}</p>"
        f"{job_line}"
        f"{import_block}"
        "<ol style='line-height:1.45;'>"
        f"{items}"
        "</ol>"
        "<p style='color:#bfdbfe;'>Der Builder ist absichtlich freigabeorientiert: "
        "Produktive Aktivierung passiert erst nach Tests und Deiner Entscheidung.</p>"
        f"<details><summary>Originalauftrag</summary><pre style='white-space:pre-wrap'>{html.escape(str(query or ''))}</pre></details>"
        "</section>"
    )


def _plan_rows(action: str, import_result=None):
    if action == "import":
        return [
            ("1", "Quelle pruefen", "Agentenordner oder Uebersichtsdatei lesen, Herkunft und Grenzen dokumentieren."),
            ("2", "Relevantes sichern", "Markdown, JSON/YAML, Skripte und Konfigurationen als Snapshot in skills/staging ablegen."),
            ("3", "Subagenten erkennen", "Unterordner und Uebersichtsdateien als abhaengige Subagenten markieren."),
            ("4", "Staging-Skill erzeugen", "Manifest, Platzhalter-Script, Importbericht und Smoke-Test anlegen."),
            ("5", "Validieren & Freigeben", "Tests ausfuehren, Rechte setzen, danach erst per Freigabe promoten."),
        ]
    if action == "edit":
        return [
            ("1", "Bestehenden Agenten identifizieren", "Skill-ID, Hauptagent und ggf. Subagenten eindeutig festlegen."),
            ("2", "Aenderungsziel beschreiben", "Was soll neu, anders oder stabiler werden? Welche Rechte bleiben tabu?"),
            ("3", "Tests/Quality-Gates definieren", "Mindestens ein reproduzierbarer Vorher/Nachher-Test."),
            ("4", "Staging-Aenderung bauen", "Aenderung separat vorbereiten, nicht direkt produktiv ueberschreiben."),
            ("5", "Review & Freigabe", "Erst nach erfolgreichem Test und Deiner Freigabe produktiv uebernehmen."),
        ]
    return [
        ("1", "Anforderung erfassen", "Was soll der Agent koennen, welche Trigger, welche Grenzen?"),
        ("2", "Plan erstellen", "Harness, Rechte, Pfade, Tests und Quality-Gates festlegen."),
        ("3", "Staging bauen", "Code, Manifest, Beispiele und lokale Tests in skills/staging ablegen."),
        ("4", "Validieren", "Tests ausfuehren, Ergebnis pruefen, Rechte- und Freigabecheck."),
        ("5", "Freigabe & Release", "Nach Deiner Freigabe nach personal/shared promoten und katalogisieren."),
    ]


def _source_path_from_context(query: str, context: dict) -> Optional[Path]:
    for attachment in context.get("attachments") or []:
        path = attachment.get("path") if isinstance(attachment, dict) else ""
        if path:
            return Path(str(path)).expanduser()

    text = str(query or "")
    quoted = re.findall(r"['\"]([^'\"]+)['\"]", text)
    for candidate in quoted:
        path = Path(candidate).expanduser()
        if path.exists():
            return path

    path_match = re.search(r"(?:file://)?(/Users/[^\n\r]+|/[^\n\r]+)", text)
    if path_match:
        raw = path_match.group(1).strip().rstrip(".,)")
        path = Path(raw).expanduser()
        if path.exists():
            return path
        parts = raw.split()
        while len(parts) > 1:
            parts.pop()
            path = Path(" ".join(parts)).expanduser()
            if path.exists():
                return path
    return None


def _stage_agent_import(source_path: Path, query: str, job_id: str) -> dict:
    source_path = source_path.expanduser().resolve()
    source_root = source_path if source_path.is_dir() else source_path.parent
    title = _agent_title_from_source(source_path)
    skill_id = _unique_skill_id(_repo_root() / "skills" / "staging", "import-" + _slug(title))
    target = _repo_root() / "skills" / "staging" / skill_id
    snapshot = target / "source_snapshot"
    tests_dir = target / "tests"
    snapshot.mkdir(parents=True)
    tests_dir.mkdir(parents=True)

    copied = _copy_relevant_files(source_root, snapshot)
    subagents = _detect_subagents(source_root)
    manifest = {
        "id": skill_id,
        "name": f"Import {title}",
        "version": "0.1.0",
        "tier": "staging",
        "description": f"Staging-Import aus {source_path}",
        "triggers": [_slug(title).replace("-", " "), title],
        "allowed_tools": ["filesystem"],
        "allowed_paths": [str(source_root)],
        "requires_approval": ["activate_skill"],
        "tests": ["tests/test_import_placeholder.py"],
        "status": "staging",
        "script": "script.py",
        "risk_level": "medium",
        "source": "agent-import",
        "source_agent_path": str(source_path),
        "parent_agent": "",
        "subagents": subagents,
        "job_id": job_id,
    }
    (target / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (target / "script.py").write_text(_placeholder_script(title), encoding="utf-8")
    (tests_dir / "test_import_placeholder.py").write_text(
        "def test_import_placeholder_manifest_exists():\n"
        "    from pathlib import Path\n"
        "    assert (Path(__file__).resolve().parents[1] / 'manifest.json').is_file()\n",
        encoding="utf-8",
    )
    (target / "README_IMPORT.md").write_text(
        _import_readme(title, source_path, copied, subagents, query),
        encoding="utf-8",
    )
    return {
        "ok": True,
        "skill_id": skill_id,
        "staging_path": str(target),
        "source_path": str(source_path),
        "copied_files": copied,
        "subagents": subagents,
    }


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _agent_title_from_source(path: Path) -> str:
    if path.is_file() and path.stem.casefold() in {"readme", "overview", "uebersicht", "übersicht"}:
        return path.parent.name
    return path.stem if path.is_file() else path.name


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "agent").casefold()).strip("-")
    return slug[:48] or "agent"


def _unique_skill_id(staging_root: Path, base: str) -> str:
    staging_root.mkdir(parents=True, exist_ok=True)
    candidate = base[:58]
    counter = 2
    while (staging_root / candidate).exists():
        suffix = f"-{counter}"
        candidate = f"{base[:58 - len(suffix)]}{suffix}"
        counter += 1
    return candidate


def _copy_relevant_files(source_root: Path, snapshot_root: Path) -> list[str]:
    copied = []
    total_bytes = 0
    for path in sorted(source_root.rglob("*")):
        if len(copied) >= MAX_SNAPSHOT_FILES or total_bytes >= MAX_SNAPSHOT_BYTES:
            break
        if not path.is_file() or path.suffix.casefold() not in RELEVANT_SUFFIXES:
            continue
        if any(part.startswith(".") or part in {"__pycache__", "node_modules"} for part in path.parts):
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size > 256 * 1024 or total_bytes + size > MAX_SNAPSHOT_BYTES:
            continue
        relative = path.relative_to(source_root)
        target = snapshot_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied.append(str(relative))
        total_bytes += size
    return copied


def _detect_subagents(source_root: Path) -> list[str]:
    result = []
    for child in sorted(source_root.iterdir() if source_root.is_dir() else []):
        if not child.is_dir() or child.name.startswith("."):
            continue
        marker_names = {
            "agent.md",
            "agents.md",
            "readme.md",
            "README.md",
            "uebersicht.md",
            "übersicht.md",
            "overview.md",
        }
        has_marker = any((child / marker).is_file() for marker in marker_names)
        has_script = any((child / name).is_file() for name in ("script.py", "workflow.yaml", "workflow.yml"))
        if has_marker or has_script:
            result.append(child.name)
    return result


def _placeholder_script(title: str) -> str:
    safe_title = repr(title)
    return (
        "\"\"\"Staging placeholder for an imported Trinity agent.\"\"\"\n\n"
        "def can_handle(query):\n"
        "    return False\n\n"
        "def execute(query, context=None):\n"
        f"    title = {safe_title}\n"
        "    return {\n"
        "        'direct_answer': (\n"
        "            f'Der importierte Agent {title} liegt im Staging. '\n"
        "            'Bitte erst Importbericht, Tests und Freigabe pruefen.'\n"
        "        )\n"
        "    }\n"
    )


def _import_readme(title: str, source_path: Path, copied: list[str], subagents: list[str], query: str) -> str:
    copied_lines = "\n".join(f"- {item}" for item in copied) or "- Keine relevanten Dateien kopiert."
    subagent_lines = "\n".join(f"- {item}" for item in subagents) or "- Keine Subagenten automatisch erkannt."
    return (
        f"# Import: {title}\n\n"
        f"- Quelle: `{source_path}`\n"
        f"- Importiert am: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        "## Erkannte Subagenten\n\n"
        f"{subagent_lines}\n\n"
        "## Kopierte Snapshot-Dateien\n\n"
        f"{copied_lines}\n\n"
        "## Naechste Quality Gates\n\n"
        "1. Quelle und Snapshot fachlich pruefen.\n"
        "2. Manifest-Rechte, Pfade und Freigaben einschaetzen.\n"
        "3. Echte Tests ergaenzen.\n"
        "4. Erst nach Freigabe nach `skills/personal` oder `skills/shared` promoten.\n\n"
        "## Originalauftrag\n\n"
        f"```text\n{query}\n```\n"
    )


def _import_block(import_result) -> str:
    if not import_result:
        return ""
    if not import_result.get("ok"):
        return (
            "<aside style='border:1px solid #f59e0b; padding:12px; border-radius:12px;'>"
            f"{html.escape(import_result.get('message', 'Quelle fehlt.'))}"
            "</aside>"
        )
    subagents = import_result.get("subagents") or []
    subagent_text = ", ".join(subagents) if subagents else "keine automatisch erkannt"
    return (
        "<aside style='border:1px solid #38bdf8; padding:12px; border-radius:12px; margin:12px 0;'>"
        f"<p><strong>Staging-Skill:</strong> {html.escape(import_result['skill_id'])}</p>"
        f"<p><strong>Quelle:</strong> {html.escape(import_result['source_path'])}</p>"
        f"<p><strong>Ziel:</strong> {html.escape(import_result['staging_path'])}</p>"
        f"<p><strong>Subagenten:</strong> {html.escape(subagent_text)}</p>"
        "</aside>"
    )

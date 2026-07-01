"""Shared Agentenbuilder skill for Trinity's controlled agent forge."""

import html
import importlib.util
import json
import py_compile
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Optional


PRIORITY = 99

TRIGGER_PATTERNS = (
    r"\bagentenbuilder\b",
    r"\bagent builder\b",
    r"\b(?:baue|erstelle|entwickle)\s+(?:einen\s+)?agenten\b",
    r"\b(?:importiere|importier|uebernimm|übernimm|hol(?:e)?\s+dir)\s+(?:diesen\s+|den\s+|einen\s+)?agenten\b",
    r"\b(?:hier\s+(?:ist|liegt)|schau\s+mal)\s+(?:ein\s+)?agent(?:enordner)?\b",
    r"\bagent(?:enordner)?\b.*\b(?:trinity|lauffaehig|lauffähig|moeglich|möglich|nutzbar|einbinden|integrieren)\b",
    r"\b(?:mach|mache)\s+(?:ihn|den|diesen|diesen\s+agenten|den\s+agenten)?\s*(?:fuer|für)\s+trinity\s+(?:moeglich|möglich|lauffaehig|lauffähig|nutzbar)\b",
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
    "hier ist ein agent",
    "hier liegt ein agent",
    "schau mal ein agent",
    "agentenordner",
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

    staging_result = None
    if action == "import":
        source_path = _source_path_from_context(query, context)
        if source_path and source_path.exists():
            staging_result = _stage_agent_import(source_path, query, job_id, context)
        else:
            staging_result = {
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
    else:
        staging_result = _stage_agent_request(action, query, job_id, context)

    builder_result = _run_builder_loop(query, context, action, staging_result)
    message = _direct_message(action, staging_result, builder_result)

    html_payload = _html_payload(
        title=title,
        query=query,
        job_id=(builder_result or {}).get("job_id") or job_id,
        route=route,
        action=action,
        import_result=staging_result,
        builder_result=builder_result,
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
    if any(pattern in text for pattern in IMPORT_PATTERNS) or _looks_like_agent_import_request(text):
        return "import"
    if any(pattern in text for pattern in EDIT_PATTERNS):
        return "edit"
    return "create"


def _looks_like_agent_import_request(text: str) -> bool:
    if "agent" not in text:
        return False
    if "agentenordner" in text:
        return True
    if "trinity" not in text:
        return False
    return any(
        marker in text
        for marker in (
            "mach",
            "mache",
            "moeglich",
            "möglich",
            "lauffaehig",
            "lauffähig",
            "nutzbar",
            "einbinden",
            "integrieren",
            "uebernehmen",
            "übernehmen",
        )
    )


def _direct_message(action: str, import_result, builder_result=None) -> str:
    job_id = (builder_result or {}).get("job_id", "")
    status = (builder_result or {}).get("status", "")
    job_suffix = f" Builder-Job: {job_id} ({status})." if job_id else ""
    if action == "import" and import_result:
        if import_result.get("ok"):
            return (
                "Ich habe den Agentenimport als BrainVault-Draft vorbereitet und "
                f"die Quality-Gates im Builder-Loop gestartet. Skill-ID: {import_result['skill_id']}."
                f"{job_suffix} Aktiv wird der Agent erst nach Validierung und Deiner Freigabe."
            )
        return "Ich habe den Agentenimport vorbereitet, brauche aber noch eine eindeutige Quelle."
    if action == "edit":
        return (
            "Ich habe fuer die Aenderung oder Erweiterung einen Staging-Entwurf "
            f"angelegt und den Builder-Loop gestartet.{job_suffix} Nach Tests und "
            "Freigabe kann daraus die produktive Agentenversion werden."
        )
    return (
        "Ich habe den Agentenbuilder aktiviert, einen BrainVault-Draft angelegt "
        f"und die Quality-Gates vorbereitet.{job_suffix} Produktive Aktivierung "
        "passiert erst nach Deiner Freigabe."
    )


def _html_payload(
    title: str,
    query: str,
    job_id: str,
    route: str,
    action: str,
    import_result=None,
    builder_result=None,
) -> str:
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
    builder_block = _builder_block(builder_result)
    return (
        "<section style='font-family: system-ui; padding: 20px; color: #e8f3ff; "
        "background: linear-gradient(135deg,#111827,#172554); border-radius: 16px;'>"
        "<h2 style='margin-top:0;'>Trinity Agentenbuilder</h2>"
        f"<p><strong>Auftrag:</strong> {html.escape(title)}</p>"
        f"<p><strong>Modus:</strong> {html.escape(action)}</p>"
        f"{job_line}"
        f"{import_block}"
        f"{builder_block}"
        "<ol style='line-height:1.45;'>"
        f"{items}"
        "</ol>"
        "<p style='color:#bfdbfe;'>Der Builder ist absichtlich freigabeorientiert: "
        "Produktive Aktivierung passiert erst nach Tests und Deiner Entscheidung.</p>"
        f"<details><summary>Originalauftrag</summary><pre style='white-space:pre-wrap'>{html.escape(str(query or ''))}</pre></details>"
        "</section>"
    )


def _stage_agent_request(action: str, query: str, job_id: str, context: Optional[dict] = None) -> dict:
    title = _title_from_request(query, action)
    skill_id = _unique_brainvault_agent_id(context or {}, "draft", f"{action}-" + _slug(title))
    target = _brainvault_agents_root(context or {}) / "draft" / skill_id
    tests_dir = target / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    agent_id = f"draft.{skill_id.replace('-', '_')}"
    _write_agent_yaml(
        target / "agent.yaml",
        _brainvault_agent_yaml(
            agent_id=agent_id,
            name=f"{'Aenderung' if action == 'edit' else 'Entwurf'} {title}",
            description=f"Agentenbuilder-Draft fuer Auftrag: {_short_title(query)}",
            relative_path=f".agents/draft/{skill_id}",
            source_paths=[],
            triggers=[_slug(title).replace("-", " "), title],
        ),
    )
    manifest = {
        "id": agent_id,
        "name": f"{'Aenderung' if action == 'edit' else 'Entwurf'} {title}",
        "version": "0.1.0",
        "tier": "brainvault",
        "description": f"Agentenbuilder-Draft fuer Auftrag: {_short_title(query)}",
        "triggers": [_slug(title).replace("-", " "), title],
        "allowed_tools": ["filesystem", "tests"],
        "allowed_paths": [".agents/draft", "TrinityRuntime/jobs"],
        "requires_approval": ["activate_skill"],
        "tests": ["tests/test_builder_placeholder.py"],
        "status": "draft",
        "script": "script.py",
        "risk_level": "medium",
        "source": f"agent-builder-{action}",
        "source_agent_path": "",
        "parent_agent": _parent_agent_from_query(query) if action == "edit" else "",
        "subagents": [],
        "job_id": job_id,
    }
    (target / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (target / "script.py").write_text(_placeholder_script(title), encoding="utf-8")
    (tests_dir / "test_builder_placeholder.py").write_text(
        "def test_builder_placeholder_manifest_exists():\n"
        "    from pathlib import Path\n"
        "    assert (Path(__file__).resolve().parents[1] / 'manifest.json').is_file()\n",
        encoding="utf-8",
    )
    (target / "README.md").write_text(
        f"# {manifest['name']}\n\n{manifest['description']}\n",
        encoding="utf-8",
    )
    (target / "SKILL.md").write_text(
        f"# {manifest['name']}\n\n## Auftrag\n\n{_short_title(query)}\n",
        encoding="utf-8",
    )
    (target / "README_BUILDER.md").write_text(
        _builder_readme(title, action, query),
        encoding="utf-8",
    )
    _rebuild_brainvault_catalog(context or {})
    return {
        "ok": True,
        "skill_id": agent_id,
        "staging_path": str(target),
        "source_path": "",
        "copied_files": [],
        "subagents": [],
        "action": action,
    }


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


def _run_builder_loop(query: str, context: dict, action: str, staging_result: dict) -> Optional[dict]:
    if not staging_result or not staging_result.get("ok"):
        return None
    jobs = _job_manager()
    if jobs is None:
        return None
    job = _ensure_builder_job(jobs, query, context, action, staging_result)
    job_id = job["job_id"]
    step_ids = _append_builder_steps(jobs, job_id, action)
    staging_path = Path(staging_result["staging_path"])
    max_attempts = _max_attempts(context)
    requested_harnesses = _requested_harnesses(query, context)
    harness_reports = []
    final_validation = {"ok": False, "errors": ["Validation wurde nicht ausgefuehrt."], "warnings": []}

    try:
        _mark_step(jobs, job_id, step_ids[0], "RUNNING", {"staging_path": str(staging_path)})
        _write_builder_plan(staging_path, query, action, requested_harnesses, max_attempts)
        _mark_step(
            jobs,
            job_id,
            step_ids[0],
            "SUCCEEDED",
            {
                "staging_path": str(staging_path),
                "skill_id": staging_result.get("skill_id", ""),
                "subagents": staging_result.get("subagents", []),
            },
        )

        for attempt in range(1, max_attempts + 1):
            _mark_step(jobs, job_id, step_ids[1], "RUNNING", {"attempt": attempt})
            final_validation = _validate_staging_skill(staging_path)
            _write_validation_report(staging_path, final_validation, attempt)
            _mark_step(
                jobs,
                job_id,
                step_ids[1],
                "SUCCEEDED" if final_validation["ok"] else "FAILED",
                {"attempt": attempt, **final_validation},
            )
            if final_validation["ok"]:
                if requested_harnesses and not harness_reports:
                    _mark_step(
                        jobs,
                        job_id,
                        step_ids[2],
                        "RUNNING",
                        {
                            "attempt": attempt,
                            "harnesses": requested_harnesses,
                            "mode": "validation_feedback",
                        },
                    )
                    harness_reports = _run_requested_harnesses(
                        query,
                        context,
                        action,
                        staging_path,
                        final_validation,
                        requested_harnesses,
                    )
                    _write_harness_report(staging_path, harness_reports)
                    _mark_step(
                        jobs,
                        job_id,
                        step_ids[2],
                        "SUCCEEDED" if harness_reports else "SKIPPED",
                        {
                            "attempt": attempt,
                            "reports": harness_reports,
                            "mode": "validation_feedback",
                        },
                    )
                    final_validation = _validate_staging_skill(staging_path)
                    _write_validation_report(staging_path, final_validation, attempt)
                break

            if not requested_harnesses:
                break
            _mark_step(
                jobs,
                job_id,
                step_ids[2],
                "RUNNING",
                {"attempt": attempt, "harnesses": requested_harnesses},
            )
            harness_reports = _run_requested_harnesses(
                query,
                context,
                action,
                staging_path,
                final_validation,
                requested_harnesses,
            )
            _write_harness_report(staging_path, harness_reports)
            if harness_reports:
                _mark_step(
                    jobs,
                    job_id,
                    step_ids[2],
                    "SUCCEEDED",
                    {"attempt": attempt, "reports": harness_reports},
                )
            else:
                _mark_step(
                    jobs,
                    job_id,
                    step_ids[2],
                    "SKIPPED",
                    {"attempt": attempt, "reason": "Kein externer Harness ausfuehrbar."},
                )

        if final_validation["ok"]:
            if not harness_reports:
                _mark_step(
                    jobs,
                    job_id,
                    step_ids[2],
                    "SKIPPED",
                    {"reason": "Kein externer Harness angefordert oder ausfuehrbar."},
                )
            _mark_step(
                jobs,
                job_id,
                step_ids[3],
                "SUCCEEDED",
                {
                    "quality_gate": "Staging-Agent ist syntaktisch und strukturell pruefbar.",
                    "promotion": "Freigabe activate_skill erforderlich.",
                },
            )
            jobs.complete(
                job_id,
                "Agentenbuilder-Loop erfolgreich abgeschlossen; Staging wartet auf Freigabe.",
                {
                    "skill_id": staging_result.get("skill_id", ""),
                    "staging_path": str(staging_path),
                    "harness_reports": harness_reports,
                },
            )
        else:
            _mark_step(
                jobs,
                job_id,
                step_ids[3],
                "FAILED",
                {
                    "quality_gate": "Staging-Agent braucht Nacharbeit.",
                    "errors": final_validation.get("errors", []),
                },
            )
            jobs.fail(
                job_id,
                "Agentenbuilder-Loop braucht Nacharbeit; Staging wurde nicht freigegeben.",
                {
                    "skill_id": staging_result.get("skill_id", ""),
                    "staging_path": str(staging_path),
                    "validation": final_validation,
                    "harness_reports": harness_reports,
                },
                escalation=True,
            )
    except Exception as exc:  # pragma: no cover - defensive job logging path
        jobs.fail(job_id, f"Agentenbuilder-Loop ist fehlgeschlagen: {exc}", escalation=True)

    final_job = jobs.get(job_id)
    return {
        "job_id": job_id,
        "status": final_job["status"],
        "validation": final_validation,
        "harnesses": requested_harnesses,
        "harness_reports": harness_reports,
        "staging_path": str(staging_path),
        "skill_id": staging_result.get("skill_id", ""),
    }


def _job_manager():
    try:
        from job_manager import JobManager
    except ImportError:
        core_path = _repo_root() / "core"
        if str(core_path) not in sys.path:
            sys.path.insert(0, str(core_path))
        try:
            from job_manager import JobManager
        except ImportError:
            return None
    return JobManager(_repo_root())


def _ensure_builder_job(jobs, query: str, context: dict, action: str, staging_result: dict) -> dict:
    existing = _existing_job_id(context)
    if existing:
        try:
            job = jobs.get(existing)
            if job["status"] == "PENDING":
                job = jobs.start(existing, "Agentenbuilder-Loop gestartet.")
            return job
        except Exception:
            pass
    return jobs.create_job(
        f"Agentenbuilder: {_short_title(query)}",
        source="agent-builder",
        route="agent_forge",
        risk_level="medium",
        plan=[],
        metadata={
            "query": str(query or ""),
            "action": action,
            "skill_id": staging_result.get("skill_id", ""),
            "staging_path": staging_result.get("staging_path", ""),
        },
    )


def _existing_job_id(context: dict) -> str:
    decision = context.get("task_decision") if isinstance(context, dict) else None
    job = getattr(decision, "job", None) if decision is not None else None
    return str((job or {}).get("job_id") or "")


def _append_builder_steps(jobs, job_id: str, action: str) -> list[str]:
    titles = [
        "Staging-Artefakte und Builder-Plan vorbereiten",
        "Lokale Quality-Gates pruefen",
        "Optionales Harness-Feedback auswerten",
        "Freigabe- und Promotion-Status festlegen",
    ]
    step_ids = []
    for title in titles:
        job = jobs.add_step(
            job_id,
            title,
            quality_gate=True,
            details={"builder_action": action},
        )
        step_ids.append(job["steps"][-1]["step_id"])
    return step_ids


def _mark_step(jobs, job_id: str, step_id: str, status: str, details: dict) -> None:
    jobs.update_step(job_id, step_id, status, details)


def _max_attempts(context: dict) -> int:
    config = _config_from_context(context)
    catalog = config.get("agent_catalog", {}).get("agents", {}) if isinstance(config, dict) else {}
    builder = catalog.get("agent-builder", {}) if isinstance(catalog, dict) else {}
    try:
        value = int(builder.get("max_attempts", config.get("agent_catalog", {}).get("default_max_attempts", 2)))
    except (TypeError, ValueError):
        value = 2
    return max(1, min(value, 5))


def _config_from_context(context: dict) -> dict:
    brain = context.get("brain") if isinstance(context, dict) else None
    if brain is not None and getattr(brain, "config_path", ""):
        try:
            with open(brain.config_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
                return data if isinstance(data, dict) else {}
        except Exception:
            pass
    return {
        "codex": context.get("codex_cfg") or {},
        "opencode": context.get("opencode_cfg") or {},
        "pi": context.get("pi_cfg") or {},
    }


def _requested_harnesses(query: str, context: dict) -> list[str]:
    text = str(query or "").casefold()
    requested = []
    for harness_id, markers in {
        "codex": ("codex", "kodeks"),
        "pi": (" mit pi", "nutze pi", " pi "),
        "opencode": ("opencode", "open code", "open-code"),
    }.items():
        if any(marker in f" {text} " for marker in markers):
            requested.append(harness_id)

    config = _config_from_context(context)
    explicit_request = bool(requested)
    if not explicit_request:
        for candidate in _builder_harness_candidates(config):
            if candidate not in requested and _harness_role_enabled(config, candidate, "agent_builder"):
                requested.append(candidate)
                break
    return [item for item in requested if _harness_enabled(context, config, item)]


def _builder_harness_candidates(config: dict) -> list[str]:
    default_builder = str(config.get("control_plane", {}).get("builder_harness", "")).strip().casefold()
    candidates = []
    # Agent construction/refactoring should be handled by the coding harness by
    # default. Pi remains the normal BrainVault execution harness; Codex is the
    # safer default for building, tests and reviewable diffs.
    if _harness_role_enabled(config, "codex", "agent_builder"):
        candidates.append("codex")
    if default_builder in {"codex", "pi", "opencode"} and default_builder not in candidates:
        candidates.append(default_builder)
    for harness_id in ("codex", "opencode", "pi"):
        if harness_id not in candidates:
            candidates.append(harness_id)
    return candidates


def _harness_role_enabled(config: dict, harness_id: str, role: str) -> bool:
    frameworks = config.get("harness_routing", {}).get("frameworks", {})
    roles = frameworks.get(harness_id, {}).get("roles", {}) if isinstance(frameworks, dict) else {}
    return bool(roles.get(role, False))


def _harness_enabled(context: dict, config: dict, harness_id: str) -> bool:
    section = config.get(harness_id, {})
    if not isinstance(section, dict) or not section.get("enabled", False):
        return False
    if harness_id == "pi":
        return True
    projects = section.get("projects", {})
    return isinstance(projects, dict) and bool(projects)


def _run_requested_harnesses(
    query: str,
    context: dict,
    action: str,
    staging_path: Path,
    validation: dict,
    harnesses: list[str],
) -> list[dict]:
    reports = []
    for harness_id in harnesses:
        report = _run_harness(harness_id, query, context, action, staging_path, validation)
        reports.append(report)
    return reports


def _run_harness(
    harness_id: str,
    query: str,
    context: dict,
    action: str,
    staging_path: Path,
    validation: dict,
) -> dict:
    module_path = _repo_root() / "agents" / f"{harness_id}_agent" / "script.py"
    if not module_path.is_file():
        return {"harness": harness_id, "status": "skipped", "message": "Agentenmodul nicht gefunden."}
    module = _load_module(module_path, f"trinity_builder_{harness_id}")
    if module is None:
        return {"harness": harness_id, "status": "skipped", "message": "Agentenmodul konnte nicht geladen werden."}
    harness_query = _harness_query(harness_id, query, action, staging_path, validation)
    harness_context = {
        **context,
        "from_telegram": False,
        "codex_cfg": context.get("codex_cfg") or _config_from_context(context).get("codex", {}),
        "opencode_cfg": context.get("opencode_cfg") or _config_from_context(context).get("opencode", {}),
        "pi_cfg": context.get("pi_cfg") or _config_from_context(context).get("pi", {}),
    }
    try:
        result = module.execute(harness_query, harness_context)
        return {
            "harness": harness_id,
            "status": "completed",
            "message": str(result.get("direct_answer") or "")[:4000],
        }
    except Exception as exc:
        return {"harness": harness_id, "status": "failed", "message": str(exc)}


def _load_module(path: Path, module_name: str):
    try:
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception:
        return None


def _harness_query(harness_id: str, query: str, action: str, staging_path: Path, validation: dict) -> str:
    base = (
        f"Agentenbuilder-Auftrag ({action}): {query}\n\n"
        f"Staging-Pfad: {staging_path}\n"
        f"Aktuelle lokale Validierung: {json.dumps(validation, ensure_ascii=False)}\n\n"
        "Pruefe den Staging-Agenten, verbessere nur innerhalb dieses Staging-Pfads, "
        "erstelle oder aktualisiere Tests und gib am Ende einen knappen Bericht mit "
        "Plan, Aenderungen, Teststatus und offenen Blockern. Keine Promotion nach "
        "personal/shared und keine externen Aktionen."
    )
    if harness_id == "codex":
        return (
            "Trinity, nutze Codex. "
            + base
            + "\n\nHITL-Regeln fuer Codex:\n"
            "- Arbeite wie ein Builder im Review-Modus: erst Plan, dann kleine nachvollziehbare Aenderungen.\n"
            "- Wenn fachliche Entscheidungen, Rechteerweiterungen, produktive Aktivierung oder riskante Aktionen noetig waeren, stelle Rueckfragen im Abschlussbericht statt sie eigenmaechtig umzusetzen.\n"
            "- Fuehre lokale Tests aus, soweit sie ohne externe Freigabe moeglich sind.\n"
            "- Schreibe nur in den Staging-Pfad und passende Builder-/Report-Dateien dort.\n"
            "- Markiere klar, was der Nutzer als naechstes freigeben oder entscheiden muss.\n"
        )
    if harness_id == "opencode":
        return "Trinity, nutze OpenCode. " + base
    return "Trinity, nutze Pi. " + base


def _validate_staging_skill(staging_path: Path) -> dict:
    errors = []
    warnings = []
    agent_yaml_path = staging_path / "agent.yaml"
    manifest_path = staging_path / "manifest.json"
    script_path = staging_path / "script.py"
    manifest = {}
    if agent_yaml_path.is_file():
        try:
            agent_yaml = _load_agent_yaml(agent_yaml_path)
        except Exception as exc:
            agent_yaml = {}
            errors.append(f"agent.yaml ist ungueltig: {exc}")
        if agent_yaml:
            for key in ("id", "name", "source", "execution_scope", "status", "path"):
                if not agent_yaml.get(key):
                    errors.append(f"agent.yaml: Feld {key} fehlt.")
            if agent_yaml.get("source") != "brainvault":
                errors.append("agent.yaml: source muss brainvault sein.")
            if agent_yaml.get("execution_scope") != "shared_harness":
                errors.append("agent.yaml: execution_scope muss shared_harness sein.")
            if agent_yaml.get("status") not in {"draft", "active", "disabled", "archived"}:
                errors.append("agent.yaml: status ist ungueltig.")
        if not (staging_path / "SKILL.md").is_file():
            warnings.append("SKILL.md fehlt im BrainVault-Agentenordner.")
        if not (staging_path / "README.md").is_file():
            warnings.append("README.md fehlt im BrainVault-Agentenordner.")
    if not manifest_path.is_file():
        if not agent_yaml_path.is_file():
            errors.append("manifest.json oder agent.yaml fehlt.")
    else:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"manifest.json ist ungueltig: {exc}")
    if manifest:
        for key in ("id", "name", "tier", "status", "script"):
            if not manifest.get(key):
                errors.append(f"manifest.json: Feld {key} fehlt.")
        if manifest.get("tier") not in {"staging", "brainvault"}:
            errors.append("manifest.json: tier muss staging oder brainvault sein.")
        if manifest.get("tier") == "brainvault" and manifest.get("status") not in {"draft", "active", "disabled", "archived"}:
            errors.append("manifest.json: brainvault status ist ungueltig.")
        if manifest.get("tier") == "staging" and manifest.get("status") != "staging":
            warnings.append("manifest.json: Staging-Skill sollte status staging haben.")
        for test_path in manifest.get("tests") or []:
            if not (staging_path / str(test_path)).is_file():
                errors.append(f"Test fehlt: {test_path}")
    if not script_path.is_file():
        errors.append("script.py fehlt.")
    else:
        try:
            py_compile.compile(str(script_path), doraise=True)
        except py_compile.PyCompileError as exc:
            errors.append(f"script.py kompiliert nicht: {exc.msg}")
    if (staging_path / "source_snapshot").is_dir():
        if not any((staging_path / "source_snapshot").rglob("*")):
            warnings.append("source_snapshot ist leer.")
    if not ((staging_path / "README_IMPORT.md").is_file() or (staging_path / "README_BUILDER.md").is_file()):
        warnings.append("Import- oder Builder-README fehlt.")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def _write_builder_plan(staging_path: Path, query: str, action: str, harnesses: list[str], max_attempts: int) -> None:
    lines = [
        "# Builder Plan",
        "",
        f"- Aktion: {action}",
        f"- Maximalversuche: {max_attempts}",
        f"- Angefragte Harnesses: {', '.join(harnesses) if harnesses else 'keine'}",
        "",
        "## Quality Gates",
        "",
        "1. Staging-Manifest ist gueltiges JSON.",
        "2. Skill bleibt im Tier `staging`.",
        "3. Runner-Script kompiliert.",
        "4. Manifest-Tests existieren.",
        "5. Produktive Aktivierung bleibt gesperrt bis `activate_skill` freigegeben ist.",
        "",
        "## Originalauftrag",
        "",
        "```text",
        str(query or ""),
        "```",
    ]
    (staging_path / "BUILDER_PLAN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_validation_report(staging_path: Path, validation: dict, attempt: int) -> None:
    errors = "\n".join(f"- {item}" for item in validation.get("errors", [])) or "- Keine"
    warnings = "\n".join(f"- {item}" for item in validation.get("warnings", [])) or "- Keine"
    text = (
        "# Validation Report\n\n"
        f"- Versuch: {attempt}\n"
        f"- Ergebnis: {'OK' if validation.get('ok') else 'NACHARBEIT'}\n\n"
        "## Fehler\n\n"
        f"{errors}\n\n"
        "## Hinweise\n\n"
        f"{warnings}\n"
    )
    (staging_path / "VALIDATION_REPORT.md").write_text(text, encoding="utf-8")


def _write_harness_report(staging_path: Path, reports: list[dict]) -> None:
    if not reports:
        return
    body = ["# Harness Report", ""]
    for report in reports:
        body.extend(
            [
                f"## {report.get('harness', 'Harness')}",
                "",
                f"- Status: {report.get('status', '')}",
                "",
                "```text",
                str(report.get("message", "")),
                "```",
                "",
            ]
        )
    (staging_path / "HARNESS_REPORT.md").write_text("\n".join(body), encoding="utf-8")


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


def _stage_agent_import(source_path: Path, query: str, job_id: str, context: Optional[dict] = None) -> dict:
    source_path = source_path.expanduser().resolve()
    source_root = source_path if source_path.is_dir() else source_path.parent
    title = _agent_title_from_source(source_path)
    skill_id = _unique_brainvault_agent_id(context or {}, _area_from_source(source_path), _slug(title))
    area = _area_from_source(source_path)
    target = _brainvault_agents_root(context or {}) / area / skill_id
    snapshot = target / "origin_snapshot"
    tests_dir = target / "tests"
    snapshot.mkdir(parents=True)
    tests_dir.mkdir(parents=True)

    copied = _copy_relevant_files(source_root, snapshot)
    subagents = _detect_subagents(source_root)
    agent_id = f"{area}.{skill_id.replace('-', '_')}"
    _write_agent_yaml(
        target / "agent.yaml",
        _brainvault_agent_yaml(
            agent_id=agent_id,
            name=title,
            description=f"Importierter BrainVault-Agent aus {source_path}",
            relative_path=f".agents/{area}/{skill_id}",
            source_paths=[str(source_path)],
            triggers=[_slug(title).replace("-", " "), title],
        ),
    )
    manifest = {
        "id": agent_id,
        "name": f"Import {title}",
        "version": "0.1.0",
        "tier": "brainvault",
        "description": f"BrainVault-Draft-Import aus {source_path}",
        "triggers": [_slug(title).replace("-", " "), title],
        "allowed_tools": ["filesystem"],
        "allowed_paths": [str(source_root)],
        "requires_approval": ["activate_skill"],
        "tests": ["tests/test_import_placeholder.py"],
        "status": "draft",
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
    (target / "README.md").write_text(
        f"# {title}\n\nImportierter BrainVault-Agent aus `{source_path}`.\n",
        encoding="utf-8",
    )
    (target / "SKILL.md").write_text(
        f"# {title}\n\n## Herkunft\n\n`{source_path}`\n\n## Status\n\nDraft bis Validierung und Freigabe abgeschlossen sind.\n",
        encoding="utf-8",
    )
    (target / "README_IMPORT.md").write_text(
        _import_readme(title, source_path, copied, subagents, query),
        encoding="utf-8",
    )
    _rebuild_brainvault_catalog(context or {})
    return {
        "ok": True,
        "skill_id": agent_id,
        "staging_path": str(target),
        "source_path": str(source_path),
        "copied_files": copied,
        "subagents": subagents,
    }


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _brainvault_root(context: dict) -> Path:
    config = _config_from_context(context)
    try:
        core_path = _repo_root() / "core"
        if str(core_path) not in sys.path:
            sys.path.insert(0, str(core_path))
        from brainvault_agents import brainvault_root_from_config, ensure_brainvault_layout

        root = brainvault_root_from_config(_repo_root(), config)
        ensure_brainvault_layout(root)
        return root
    except Exception:
        control = config.get("control_plane", {}) if isinstance(config, dict) else {}
        value = control.get("brainvault_root") or control.get("vault_root")
        if value:
            path = Path(str(value)).expanduser().resolve()
            if path.name.casefold() == "trinityvault":
                path = path.parent
            (path / ".agents").mkdir(parents=True, exist_ok=True)
            return path
        fallback = _repo_root() / "BrainVault"
        (fallback / ".agents").mkdir(parents=True, exist_ok=True)
        return fallback


def _brainvault_agents_root(context: dict) -> Path:
    root = _brainvault_root(context)
    agents = root / ".agents"
    agents.mkdir(parents=True, exist_ok=True)
    return agents


def _rebuild_brainvault_catalog(context: dict) -> None:
    try:
        core_path = _repo_root() / "core"
        if str(core_path) not in sys.path:
            sys.path.insert(0, str(core_path))
        from brainvault_agents import build_catalog

        build_catalog(_brainvault_root(context))
    except Exception:
        return


def _unique_brainvault_agent_id(context: dict, area: str, base: str) -> str:
    root = _brainvault_agents_root(context) / _slug(area)
    root.mkdir(parents=True, exist_ok=True)
    clean = _slug(base)
    candidate = clean[:58]
    counter = 2
    while (root / candidate).exists():
        suffix = f"-{counter}"
        candidate = f"{clean[:58 - len(suffix)]}{suffix}"
        counter += 1
    return candidate


def _area_from_source(path: Path) -> str:
    parts = [part.casefold() for part in path.parts]
    for marker in ("campushub", "ideaverse", "mainhub"):
        if marker in parts:
            return _slug(marker)
    return "imported"


def _brainvault_agent_yaml(
    agent_id: str,
    name: str,
    description: str,
    relative_path: str,
    source_paths: list[str],
    triggers: list[str],
) -> dict:
    return {
        "id": agent_id,
        "name": name,
        "version": "0.1.0",
        "source": "brainvault",
        "execution_scope": "shared_harness",
        "status": "draft",
        "enabled": False,
        "created_at": time.strftime("%Y-%m-%d"),
        "description": description,
        "path": relative_path,
        "workspace": None,
        "triggers": {
            "natural": triggers,
            "slash": [],
            "examples": [],
        },
        "tags": [agent_id.split(".", 1)[0]],
        "compatible_harnesses": ["trinity", "codex", "pi", "opencode", "claude-code", "antigravity"],
        "preferred_harness": "auto",
        "entrypoints": {"script": "script.py"},
        "permissions": {
            "read": [],
            "write": [],
            "approval_required": ["activate_skill"],
            "forbidden": ["destructive_changes_without_approval", "secret_logging"],
        },
        "secrets": [],
        "outputs": [],
        "resources": {"max_parallel_runs": 1},
        "validation": {"tests_required": True, "last_validated": None},
        "origin": {"source_paths": source_paths},
    }


def _write_agent_yaml(path: Path, data: dict) -> None:
    try:
        core_path = _repo_root() / "core"
        if str(core_path) not in sys.path:
            sys.path.insert(0, str(core_path))
        from brainvault_agents import write_agent_yaml

        write_agent_yaml(path, data)
    except Exception:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_agent_yaml(path: Path) -> dict:
    core_path = _repo_root() / "core"
    if str(core_path) not in sys.path:
        sys.path.insert(0, str(core_path))
    from brainvault_agents import load_agent_yaml

    return load_agent_yaml(path)


def _agent_title_from_source(path: Path) -> str:
    if path.is_file() and path.stem.casefold() in {"readme", "overview", "uebersicht", "übersicht"}:
        return path.parent.name
    return path.stem if path.is_file() else path.name


def _title_from_request(query: str, action: str) -> str:
    text = " ".join(str(query or "").split())
    patterns = [
        r"agenten?\s+(?:fuer|für|zu|um)\s+(.+)$",
        r"(?:baue|erstelle|entwickle|erweitere|verbessere)\s+(?:einen\s+|den\s+)?(.+?agent(?:en)?)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            value = match.group(1).strip(" .,:;")
            if value:
                return value[:80]
    return "Agentenaenderung" if action == "edit" else "Neuer Agent"


def _parent_agent_from_query(query: str) -> str:
    text = " ".join(str(query or "").split())
    match = re.search(
        r"(?:erweitere|verbessere|aendere|ändere)\s+(?:den\s+|die\s+|das\s+)?(.+?agent(?:en)?)\b",
        text,
        flags=re.IGNORECASE,
    )
    return match.group(1).strip(" .,:;") if match else ""


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
        relative = path.relative_to(source_root)
        if any(part.startswith(".") or part in {"__pycache__", "node_modules"} for part in relative.parts):
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size > 256 * 1024 or total_bytes + size > MAX_SNAPSHOT_BYTES:
            continue
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


def _builder_readme(title: str, action: str, query: str) -> str:
    return (
        f"# Builder-Staging: {title}\n\n"
        f"- Aktion: `{action}`\n"
        f"- Erstellt am: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        "- Status: Staging, nicht produktiv aktiviert\n\n"
        "## Ziel\n\n"
        "Dieser Ordner ist ein kontrollierter Entwurf fuer einen neuen oder "
        "zu erweiternden Trinity-Agenten. Der Builder-Loop darf hier planen, "
        "Tests ergaenzen und die Struktur verbessern. Produktiv wird der Agent "
        "erst nach expliziter Freigabe.\n\n"
        "## Naechste Quality Gates\n\n"
        "1. Agentenvertrag und Trigger praezisieren.\n"
        "2. Mindestens einen reproduzierbaren Test ergaenzen.\n"
        "3. Rechte, erlaubte Pfade und Freigaben pruefen.\n"
        "4. Optional Codex/Pi/OpenCode-Harnessbericht einholen.\n"
        "5. Erst nach Freigabe nach `skills/personal` oder `skills/shared` promoten.\n\n"
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


def _builder_block(builder_result) -> str:
    if not builder_result:
        return ""
    validation = builder_result.get("validation") or {}
    errors = validation.get("errors") or []
    warnings = validation.get("warnings") or []
    status_color = "#22c55e" if validation.get("ok") else "#f59e0b"
    harnesses = builder_result.get("harnesses") or []
    return (
        "<aside style='border:1px solid #334155; padding:12px; border-radius:12px; margin:12px 0;'>"
        f"<p><strong>Builder-Job:</strong> {html.escape(builder_result.get('job_id', ''))} "
        f"<span style='color:{status_color}'>({html.escape(builder_result.get('status', ''))})</span></p>"
        f"<p><strong>Quality-Gate:</strong> {'OK' if validation.get('ok') else 'Nacharbeit noetig'}</p>"
        f"<p><strong>Harnesses:</strong> {html.escape(', '.join(harnesses) if harnesses else 'keine externen Harnesses gestartet')}</p>"
        f"<p><strong>Fehler:</strong> {html.escape(str(len(errors)))} · "
        f"<strong>Hinweise:</strong> {html.escape(str(len(warnings)))}</p>"
        f"<p><strong>Staging:</strong> {html.escape(builder_result.get('staging_path', ''))}</p>"
        "</aside>"
    )

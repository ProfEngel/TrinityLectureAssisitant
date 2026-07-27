"""Local agent workbench exposed through Trinity's existing HTTP bridge."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Optional

from job_manager import JobManager
from platform_adapters import find_opencode_executable


MAX_UPLOAD_BYTES = 30 * 1024 * 1024
THESIS_TILE_ID = "thesis-reviewer"


class WorkbenchManager:
    """Catalog and execute explicit, form-driven agent jobs."""

    def __init__(self, home: str | Path):
        self.home = Path(home).resolve()
        self.jobs = JobManager(self.home)
        self.upload_root = self.home / "memory" / "workbench_uploads"
        self._threads: dict[str, threading.Thread] = {}
        self._lock = threading.Lock()

    def catalog(self, config: dict, profile: str) -> dict:
        opencode = config.get("opencode", {})
        projects = self._configured_projects(opencode)
        normalized_profile = str(profile or "PRIVAT").upper()
        thesis_available = normalized_profile == "BIZ"
        return {
            "ok": True,
            "title": "Trinity-Werkstatt",
            "profile": normalized_profile,
            "harnesses": [
                {
                    "id": "opencode",
                    "name": "OpenCode",
                    "available": bool(
                        opencode.get("enabled") and find_opencode_executable()
                    ),
                    "description": (
                        "Nutzt den laufenden OpenCode-Dienst oder startet "
                        "einen geschützten lokalen Lauf."
                    ),
                }
            ],
            "models": self._opencode_models(opencode),
            "projects": [
                {"id": alias, "name": alias, "path": str(path)}
                for alias, path in projects.items()
            ],
            "default_project": str(opencode.get("default_project") or ""),
            "default_model": str(opencode.get("model") or ""),
            "categories": [
                {
                    "id": "begutachten",
                    "name": "Begutachten",
                    "tiles": [
                        {
                            "id": THESIS_TILE_ID,
                            "title": "Abschlussarbeit begutachten",
                            "subtitle": (
                                "Strukturiertes Erst- oder Zweitgutachten mit "
                                "Literatur- und Integritätsprüfung"
                            ),
                            "icon": "document-check",
                            "status": (
                                "bereit" if thesis_available else "nur im Profil BIZ"
                            ),
                            "available": thesis_available,
                            "profiles": ["BIZ"],
                            "agent": "thesis-reviewer",
                            "compatible_harnesses": ["opencode"],
                        }
                    ],
                },
                {
                    "id": "lehre",
                    "name": "Lehre & Präsentationen",
                    "tiles": [],
                },
                {
                    "id": "schreiben",
                    "name": "Schreiben & Veröffentlichen",
                    "tiles": [],
                },
                {
                    "id": "organisation",
                    "name": "Organisation",
                    "tiles": [],
                },
            ],
        }

    def submit(self, payload: dict, config: dict, profile: str) -> dict:
        if not isinstance(payload, dict):
            raise ValueError("Der Werkstatt-Auftrag muss ein Objekt sein.")
        tile_id = str(payload.get("tile_id") or "").strip()
        if tile_id != THESIS_TILE_ID:
            raise ValueError("Diese Werkstatt-Kachel ist noch nicht verfügbar.")
        if str(profile or "").upper() != "BIZ":
            raise PermissionError(
                "Der Gutachter verarbeitet BIZ-Daten und ist nur im Profil BIZ freigegeben."
            )
        harness = str(payload.get("harness") or "opencode").strip().casefold()
        if harness != "opencode":
            raise ValueError("Der Gutachter-Pilot ist derzeit für OpenCode freigegeben.")

        opencode = config.get("opencode", {})
        if not opencode.get("enabled"):
            raise ValueError("OpenCode ist in Trinity noch nicht aktiviert.")
        executable = find_opencode_executable()
        if not executable:
            raise ValueError("OpenCode wurde auf diesem Rechner nicht gefunden.")

        projects = self._configured_projects(opencode)
        alias = str(
            payload.get("project")
            or opencode.get("default_project")
            or (next(iter(projects)) if len(projects) == 1 else "")
        ).strip()
        project_path = projects.get(alias)
        if project_path is None:
            raise ValueError(
                "Bitte wähle einen in Trinity freigegebenen OpenCode-Projektordner."
            )

        review_type = str(payload.get("review_type") or "erstgutachten").strip()
        if review_type not in {"erstgutachten", "zweitgutachten"}:
            raise ValueError("Bitte Erstgutachten oder Zweitgutachten wählen.")
        attachments = payload.get("attachments") or []
        thesis = [item for item in attachments if item.get("role") == "thesis"]
        if len(thesis) != 1:
            raise ValueError("Für den Gutachter wird genau eine Thesis-PDF benötigt.")

        job = self.jobs.create_job(
            title=(
                "Abschlussarbeit begutachten · "
                + ("Erstgutachten" if review_type == "erstgutachten" else "Zweitgutachten")
            ),
            source="workbench",
            route="opencode",
            risk_level="medium",
            plan=[
                {"title": "Eingaben sicher übernehmen", "quality_gate": True},
                {"title": "Gutachter-Agent mit OpenCode ausführen"},
                {"title": "Ergebnis und Pflichtbestandteile prüfen", "quality_gate": True},
                {"title": "Abschlussbericht bereitstellen", "quality_gate": True},
            ],
            metadata={
                "tile_id": tile_id,
                "agent": "thesis-reviewer",
                "harness": harness,
                "model": str(payload.get("model") or opencode.get("model") or ""),
                "project": alias,
                "profile": str(profile or ""),
                "review_type": review_type,
                "file_names": [Path(str(item.get("name") or "")).name for item in attachments],
            },
        )
        job_dir = self.upload_root / job["job_id"]
        staged = self._stage_attachments(job_dir, attachments)
        thread = threading.Thread(
            target=self._run_thesis_review,
            kwargs={
                "job_id": job["job_id"],
                "job_dir": job_dir,
                "staged": staged,
                "payload": payload,
                "opencode": opencode,
                "executable": executable,
                "project_alias": alias,
                "project_path": project_path,
                "review_type": review_type,
            },
            daemon=True,
            name=f"trinity-workbench-{job['job_id'][-8:]}",
        )
        with self._lock:
            self._threads[job["job_id"]] = thread
        thread.start()
        return {"ok": True, "job": self.public_job(job["job_id"])}

    def public_job(self, job_id: str) -> dict:
        job = self.jobs.get(str(job_id or ""))
        events = []
        for event in job.get("events", []):
            details = dict(event.get("details") or {})
            details.pop("prompt", None)
            events.append({**event, "details": details})
        return {**job, "events": events}

    @staticmethod
    def _configured_projects(config: dict) -> dict[str, Path]:
        projects = config.get("projects", {})
        if not isinstance(projects, dict):
            return {}
        result: dict[str, Path] = {}
        for raw_alias, raw_path in projects.items():
            alias = str(raw_alias).strip()
            if not alias or not raw_path:
                continue
            path = Path(
                os.path.expandvars(os.path.expanduser(str(raw_path)))
            ).resolve()
            if path.is_dir():
                result[alias] = path
        return result

    def _stage_attachments(self, job_dir: Path, attachments: list[dict]) -> list[dict]:
        job_dir.mkdir(parents=True, exist_ok=False)
        staged = []
        try:
            for index, item in enumerate(attachments):
                role = str(item.get("role") or "").strip().casefold()
                if role not in {"thesis", "docoloc"}:
                    raise ValueError("Unbekannte Anlage im Gutachter-Auftrag.")
                name = Path(str(item.get("name") or f"anlage-{index + 1}.pdf")).name
                if Path(name).suffix.casefold() != ".pdf":
                    raise ValueError("Thesis und Docoloc-Bericht müssen PDF-Dateien sein.")
                try:
                    data = base64.b64decode(
                        str(item.get("data_base64") or ""), validate=True
                    )
                except (ValueError, TypeError) as exc:
                    raise ValueError(f"{name} konnte nicht gelesen werden.") from exc
                if not data or len(data) > MAX_UPLOAD_BYTES:
                    raise ValueError(f"{name} ist leer oder größer als 30 MB.")
                target = job_dir / f"{index + 1:02d}_{name}"
                target.write_bytes(data)
                staged.append(
                    {
                        "role": role,
                        "name": name,
                        "path": target,
                        "sha256": hashlib.sha256(data).hexdigest(),
                    }
                )
        except Exception:
            shutil.rmtree(job_dir, ignore_errors=True)
            raise
        return staged

    def _run_thesis_review(
        self,
        *,
        job_id: str,
        job_dir: Path,
        staged: list[dict],
        payload: dict,
        opencode: dict,
        executable: str,
        project_alias: str,
        project_path: Path,
        review_type: str,
    ) -> None:
        try:
            current = self.jobs.start(
                job_id, "Gutachter-Auftrag wurde an OpenCode übergeben."
            )
            self.jobs.update_step(
                job_id,
                current["steps"][0]["step_id"],
                "SUCCEEDED",
                {
                    "files": [
                        {
                            "role": item["role"],
                            "name": item["name"],
                            "sha256": item["sha256"],
                        }
                        for item in staged
                    ]
                },
            )
            self.jobs.update_step(
                job_id, current["steps"][1]["step_id"], "RUNNING"
            )
            prompt = self._thesis_prompt(
                staged=staged,
                project_alias=project_alias,
                review_type=review_type,
                notes=str(payload.get("notes") or "").strip(),
            )
            output = self._run_opencode(
                executable=executable,
                project_path=project_path,
                prompt=prompt,
                attachments=[item["path"] for item in staged],
                model=str(payload.get("model") or opencode.get("model") or "").strip(),
                agent="thesis-reviewer",
                server_url=str(opencode.get("server_url") or "").strip(),
                timeout=self._bounded_int(
                    opencode.get("timeout_seconds"), 1800, 60, 7200
                ),
            )
            self.jobs.update_step(
                job_id,
                current["steps"][1]["step_id"],
                "SUCCEEDED",
                {"summary": output[-4000:]},
            )
            self.jobs.update_step(
                job_id,
                current["steps"][2]["step_id"],
                "SUCCEEDED",
                {
                    "quality_gate": (
                        "OpenCode hat einen Abschlussbericht geliefert. "
                        "Die fachliche Endfreigabe bleibt beim Nutzer."
                    )
                },
            )
            self.jobs.update_step(
                job_id,
                current["steps"][3]["step_id"],
                "SUCCEEDED",
                {"summary": output[-4000:]},
            )
            self.jobs.complete(
                job_id,
                "Gutachter-Auftrag abgeschlossen.",
                {"summary": output[-8000:]},
            )
        except Exception as exc:  # pylint: disable=broad-except
            try:
                self.jobs.fail(
                    job_id,
                    "Gutachter-Auftrag fehlgeschlagen.",
                    {"error": str(exc)[:4000]},
                )
            except ValueError:
                pass
        finally:
            shutil.rmtree(job_dir, ignore_errors=True)
            with self._lock:
                self._threads.pop(job_id, None)

    @staticmethod
    def _thesis_prompt(
        *, staged: list[dict], project_alias: str, review_type: str, notes: str
    ) -> str:
        role = "Erstgutachten" if review_type == "erstgutachten" else "Zweitgutachten"
        attachment_lines = "\n".join(
            f"- {item['role']}: {item['path']}" for item in staged
        )
        skill_path = Path.home() / ".agents" / "skills" / "thesis-reviewer" / "SKILL.md"
        return f"""Führe den installierten Agenten `thesis-reviewer` vollständig aus.

Verbindliche Agentenanweisung: {skill_path}
Zielprojekt: {project_alias}
Gutachtenart: {role}
Eingaben:
{attachment_lines}

Zusatzhinweise des Nutzers:
{notes or "(keine)"}

Lies die Agentenanweisung vollständig. Erstelle zunächst nur prüfbare Entwürfe und
die dort vorgesehenen Ergebnisdateien im Zielprojekt. Versende, veröffentliche,
verschiebe oder lösche nichts. Wenn eine Referenzvorlage, Signatur, ein Logo oder
eine fachlich notwendige Angabe fehlt, stoppe an dieser Stelle sauber und benenne
den konkreten fehlenden Bestandteil. Behaupte keine KI-Urheberschaft; kennzeichne
Plausibilitätsbefunde ausdrücklich als Indizien. Antworte abschließend auf Deutsch
mit den erzeugten Dateipfaden, dem Prüfstatus und offenen Freigaben.
"""

    @staticmethod
    def _run_opencode(
        *,
        executable: str,
        project_path: Path,
        prompt: str,
        attachments: list[Path],
        model: str,
        agent: str,
        server_url: str,
        timeout: int,
    ) -> str:
        command = [executable, "run"]
        if server_url:
            command.extend(["--attach", server_url, "--dir", str(project_path)])
        if model:
            command.extend(["--model", model])
        if agent:
            command.extend(["--agent", agent])
        for path in attachments:
            command.extend(["--file", str(path)])
        command.append(prompt)
        creation_flags = (
            getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        )
        use_shell = os.name == "nt" and str(executable).casefold().endswith(
            (".cmd", ".bat")
        )
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
            raise OSError(
                f"OpenCode wurde mit Fehlercode {completed.returncode} beendet: "
                f"{details[-2500:]}"
            )
        return (completed.stdout or "").strip()

    @staticmethod
    def _opencode_models(config: dict) -> list[dict]:
        path = Path.home() / ".config" / "opencode" / "opencode.jsonc"
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError):
            data = {}
        disabled = set(data.get("disabled_providers") or [])
        result = []
        for provider_id, provider in (data.get("provider") or {}).items():
            if provider_id in disabled or not isinstance(provider, dict):
                continue
            provider_name = str(provider.get("name") or provider_id)
            for model_id, model in (provider.get("models") or {}).items():
                display = (
                    str(model.get("name") or model_id)
                    if isinstance(model, dict)
                    else str(model_id)
                )
                result.append(
                    {
                        "id": f"{provider_id}/{model_id}",
                        "name": display,
                        "provider": provider_name,
                    }
                )
        configured = str(config.get("model") or data.get("model") or "").strip()
        if configured and not any(item["id"] == configured for item in result):
            result.insert(
                0,
                {"id": configured, "name": configured, "provider": "Konfiguriert"},
            )
        return result

    @staticmethod
    def _bounded_int(value, default: int, minimum: int, maximum: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = default
        return max(minimum, min(maximum, parsed))

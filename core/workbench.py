"""Local agent workbench exposed through Trinity's existing HTTP bridge."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import signal
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

from job_manager import JobManager
from platform_adapters import find_codex_executable, find_opencode_executable


MAX_UPLOAD_BYTES = 30 * 1024 * 1024
MAX_PRESENTATION_UPLOAD_BYTES = 60 * 1024 * 1024
THESIS_TILE_ID = "thesis-reviewer"
PRESENTATION_SCAFFOLD_TILE_ID = "html-presentation-scaffold"
PRESENTATION_BUILD_TILE_ID = "html-presentation-workshop"
PRESENTATION_MODERNIZE_TILE_ID = "html-presentation-modernize"
PRESENTATION_ALLOWED_SUFFIXES = {
    ".csv",
    ".docx",
    ".gif",
    ".html",
    ".jpeg",
    ".jpg",
    ".json",
    ".md",
    ".markdown",
    ".pdf",
    ".png",
    ".pptx",
    ".svg",
    ".txt",
    ".webp",
    ".xlsx",
}
PRESENTATION_IMAGE_MODELS = {
    "kie": [
        {
            "id": "gpt-image-2-text-to-image",
            "name": "GPT Image 2 · Text zu Bild",
        },
        {
            "id": "nano-banana-2-lite",
            "name": "Nano Banana 2 Lite · schnell",
        },
        {
            "id": "flux-2/pro-text-to-image",
            "name": "FLUX.2 Pro · Text zu Bild",
        },
    ],
}
CODEX_MODELS = [
    {
        "id": "gpt-5.6-sol",
        "name": "GPT-5.6 Sol · höchste Qualität",
        "provider": "Codex / ChatGPT",
        "harness": "codex",
    },
    {
        "id": "gpt-5.6-terra",
        "name": "GPT-5.6 Terra · ausgewogen",
        "provider": "Codex / ChatGPT",
        "harness": "codex",
    },
    {
        "id": "gpt-5.6-luna",
        "name": "GPT-5.6 Luna · schnell",
        "provider": "Codex / ChatGPT",
        "harness": "codex",
    },
    {
        "id": "gpt-5.5",
        "name": "GPT-5.5 · bisheriges Modell",
        "provider": "Codex / ChatGPT",
        "harness": "codex",
    },
]
CODEX_MODEL_IDS = {model["id"] for model in CODEX_MODELS}


class WorkbenchJobCancelled(RuntimeError):
    """Raised internally after a user cancels a running workbench job."""


class WorkbenchManager:
    """Catalog and execute explicit, form-driven agent jobs."""

    def __init__(self, home: str | Path):
        self.home = Path(home).resolve()
        self.jobs = JobManager(self.home)
        self.upload_root = self.home / "memory" / "workbench_uploads"
        self.secrets_path = self.home / "memory" / "workbench_secrets.json"
        self.presentation_resources = (
            self.home / "resources" / "html_presentation_workshop"
        )
        self._threads: dict[str, threading.Thread] = {}
        self._processes: dict[str, subprocess.Popen] = {}
        self._cancelled: set[str] = set()
        self._lock = threading.Lock()

    def catalog(self, config: dict, profile: str) -> dict:
        opencode = config.get("opencode", {})
        codex = config.get("codex", {})
        workbench = config.get("workbench", {})
        default_harness = str(
            workbench.get("default_harness") or "opencode"
        ).strip().casefold()
        if default_harness not in {"opencode", "codex"}:
            default_harness = "opencode"
        harness_configs = {"opencode": opencode, "codex": codex}
        projects_by_harness = {
            harness_id: [
                {"id": alias, "name": alias, "path": str(path)}
                for alias, path in self._configured_projects(section).items()
            ]
            for harness_id, section in harness_configs.items()
        }
        default_config = harness_configs[default_harness]
        projects = self._configured_projects(default_config)
        normalized_profile = str(profile or "PRIVAT").upper()
        presentation = workbench.get("presentation", {})
        secret_status = self.secret_status(config)
        opencode_models = [
            {**model, "harness": "opencode"}
            for model in self._opencode_models(opencode)
        ]
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
                },
                {
                    "id": "codex",
                    "name": "Codex / ChatGPT",
                    "available": bool(
                        codex.get("enabled") and find_codex_executable()
                    ),
                    "description": (
                        "Nutzt Codex mit deiner vorhandenen ChatGPT-Anmeldung "
                        "und einem ausdrücklich gewählten GPT-Modell."
                    ),
                },
            ],
            "models": opencode_models + CODEX_MODELS,
            "models_by_harness": {
                "opencode": opencode_models,
                "codex": CODEX_MODELS,
            },
            "projects": [
                {"id": alias, "name": alias, "path": str(path)}
                for alias, path in projects.items()
            ],
            "projects_by_harness": projects_by_harness,
            "default_harness": default_harness,
            "default_project": str(default_config.get("default_project") or ""),
            "default_project_by_harness": {
                harness_id: str(section.get("default_project") or "")
                for harness_id, section in harness_configs.items()
            },
            "default_model": str(
                (
                    codex.get("model")
                    if default_harness == "codex"
                    else opencode.get("model")
                )
                or ("gpt-5.6-sol" if default_harness == "codex" else "")
            ),
            "default_model_by_harness": {
                "opencode": str(opencode.get("model") or ""),
                "codex": str(codex.get("model") or "gpt-5.6-sol"),
            },
            "presentation": {
                "default_image_provider": str(
                    presentation.get("image_provider") or "kie"
                ),
                "default_image_model": str(
                    presentation.get("image_model")
                    or "gpt-image-2-text-to-image"
                ),
                "image_providers": [
                    {
                        "id": "kie",
                        "name": "Kie.ai",
                        "configured": secret_status["kie_configured"],
                        "preferred": True,
                        "models": PRESENTATION_IMAGE_MODELS["kie"],
                    },
                ],
            },
            "categories": self._catalog_categories(),
        }

    def _catalog_categories(self) -> list[dict]:
        """Return the visible roadmap in the user's preferred reading order."""

        ready = {
            "status": "bereit",
            "available": True,
            "profiles": ["BIZ", "PRIVAT", "TEST"],
        }
        return [
            {
                "id": "wissen-gestalten",
                "name": "Präsentationen, Papers und Lehrbücher",
                "tiles": [
                    {
                        **ready,
                        "id": PRESENTATION_BUILD_TILE_ID,
                        "title": "HTML-Präsentation erstellen",
                        "subtitle": (
                            "Aus Ideen und Materialien einen prüfbaren Plan und "
                            "nach Freigabe eine portable Präsentation bauen"
                        ),
                        "icon": "presentation",
                        "agent": "html-praesentationswerkstatt",
                        "compatible_harnesses": ["opencode", "codex"],
                    },
                    {
                        **ready,
                        "id": PRESENTATION_MODERNIZE_TILE_ID,
                        "title": "Vorhandene Präsentation modernisieren",
                        "subtitle": (
                            "PPTX oder PDF vollständig analysieren, Schaubilder "
                            "übernehmen und im neuen HTML-Format neu aufbauen"
                        ),
                        "icon": "presentation-import",
                        "agent": "html-praesentationswerkstatt",
                        "compatible_harnesses": ["opencode", "codex"],
                    },
                    {
                        **ready,
                        "id": PRESENTATION_SCAFFOLD_TILE_ID,
                        "title": "Präsentationsgrundgerüst anlegen",
                        "subtitle": (
                            "Visuelles Briefing, Medienablage und Review-Grundlage "
                            "in einen neuen Projektordner kopieren"
                        ),
                        "icon": "layout",
                        "status": (
                            "bereit"
                            if self._presentation_template_root().is_dir()
                            else "Vorlage fehlt"
                        ),
                        "available": self._presentation_template_root().is_dir(),
                        "agent": "html-praesentationswerkstatt",
                        "compatible_harnesses": ["trinity"],
                    },
                    self._planned_tile(
                        "textbook-workshop",
                        "Lehrbuch erstellen",
                        "Kapitel planen, recherchieren, schreiben, lektorieren und veröffentlichen",
                        agent="lehrbuchwerkstatt",
                    ),
                    self._planned_tile(
                        "paper-workshop",
                        "Paper erstellen",
                        "Wissenschaftliche Arbeiten strukturiert entwickeln und ausarbeiten",
                        status="Agent wird geprüft",
                    ),
                    self._planned_tile(
                        "research-open",
                        "Wissenschaftlich recherchieren",
                        "Offene Quellen suchen, prüfen und nachvollziehbar dokumentieren",
                    ),
                    self._planned_tile(
                        "research-hitl",
                        "Recherche mit Browser-Freigabe",
                        "Paywall-Quellen nur nach deiner sichtbaren Browser-Freigabe einbeziehen",
                        status="HITL in Vorbereitung",
                    ),
                    self._planned_tile(
                        "diagram-workshop",
                        "Schaubild erstellen",
                        "Inhalte als verständliches, editierbares Schaubild aufbereiten",
                    ),
                    self._planned_tile(
                        "infographic-workshop",
                        "Infografik erstellen",
                        "Daten und Kernaussagen als eigenständige visuelle Erklärung gestalten",
                    ),
                ],
            },
            {
                "id": "begutachten-pruefen",
                "name": "Begutachtungen und Prüfungen",
                "tiles": [
                    {
                        **ready,
                        "id": THESIS_TILE_ID,
                        "title": "Abschlussarbeit begutachten",
                        "subtitle": (
                            "Strukturiertes Erst- oder Zweitgutachten mit "
                            "Literatur- und Integritätsprüfung"
                        ),
                        "icon": "document-check",
                        "agent": "thesis-reviewer",
                        "compatible_harnesses": ["opencode", "codex"],
                    },
                    self._planned_tile(
                        "seminar-paper-review",
                        "Seminararbeit begutachten",
                        "Seminararbeiten transparent prüfen und nachvollziehbar bewerten",
                        status="Agent wird geprüft",
                    ),
                    self._planned_tile(
                        "scientific-writing-review",
                        "Wissenschaftliches Arbeiten begutachten",
                        "Aufbau, Methodik, Quellenarbeit und formale Qualität prüfen",
                        status="Agent wird geprüft",
                    ),
                ],
            },
            {
                "id": "medien",
                "name": "Medienerstellung",
                "tiles": [
                    self._planned_tile(
                        "image-cloud-workshop",
                        "Bild erstellen",
                        "Bilder über freigegebene Cloud-Modelle entwickeln",
                    ),
                    self._planned_tile(
                        "image-comfy-workshop",
                        "Bild mit ComfyUI erstellen",
                        "Lokale Workflows kontrolliert an den privaten Renderer übergeben",
                    ),
                    self._planned_tile(
                        "video-workshop",
                        "Video erstellen",
                        "Videoaufträge planen, erzeugen und prüfen",
                    ),
                    self._planned_tile(
                        "music-workshop",
                        "Musik erstellen",
                        "Musikaufträge planen, erzeugen und prüfen",
                    ),
                ],
            },
            {
                "id": "romane",
                "name": "Romanerstellung",
                "tiles": [
                    self._planned_tile(
                        "fiction-workshop",
                        "Erzählprojekt steuern",
                        "Roman, Novelle oder Kurzgeschichte planen und koordinieren",
                        agent="erzaehlwerkstatt",
                    ),
                    self._planned_tile(
                        "fiction-plot",
                        "Plot und Szenen planen",
                        "Beats, Wendepunkte, Subplots und Szenenfolgen entwickeln",
                        agent="erzaehlwerkstatt-plotarchitekt",
                    ),
                    self._planned_tile(
                        "fiction-write",
                        "Szene oder Kapitel schreiben",
                        "Fiktionale Texte in der jeweiligen Projektstimme ausarbeiten",
                        agent="erzaehlwerkstatt-romanschreiber",
                    ),
                    self._planned_tile(
                        "fiction-edit",
                        "Romantext lektorieren",
                        "Stil, Perspektive, Tempo, Dialog und Kontinuität prüfen",
                        agent="erzaehlwerkstatt-lektor",
                    ),
                    self._planned_tile(
                        "fiction-continuity",
                        "Kanon und Kontinuität prüfen",
                        "Figurenwissen, Timeline, Weltregeln und Enthüllungen abgleichen",
                        agent="erzaehlwerkstatt-chronist",
                    ),
                    self._planned_tile(
                        "fiction-visuals",
                        "Szenenbilder und Storyboards",
                        "Szenenbilder, Figurenreferenzen oder Storyboards vorbereiten",
                        agent="erzaehlwerkstatt-szenenbild",
                    ),
                    self._planned_tile(
                        "fiction-publish",
                        "Buchausgabe erstellen",
                        "Fiktion als EPUB und gesetztes PDF bauen und prüfen",
                        agent="erzaehlwerkstatt-buchausgabe",
                    ),
                ],
            },
        ]

    @staticmethod
    def _planned_tile(
        tile_id: str,
        title: str,
        subtitle: str,
        *,
        status: str = "UI in Vorbereitung",
        agent: str = "",
    ) -> dict:
        tile = {
            "id": tile_id,
            "title": title,
            "subtitle": subtitle,
            "icon": "planned",
            "status": status,
            "available": False,
            "profiles": ["BIZ", "PRIVAT", "TEST"],
            "compatible_harnesses": ["opencode", "codex"],
        }
        if agent:
            tile["agent"] = agent
        return tile

    def submit(self, payload: dict, config: dict, profile: str) -> dict:
        if not isinstance(payload, dict):
            raise ValueError("Der Werkstatt-Auftrag muss ein Objekt sein.")
        tile_id = str(payload.get("tile_id") or "").strip()
        if tile_id == THESIS_TILE_ID:
            return self._submit_thesis(payload, config, profile)
        if tile_id == PRESENTATION_SCAFFOLD_TILE_ID:
            return self._submit_presentation_scaffold(payload, config, profile)
        if tile_id in {PRESENTATION_BUILD_TILE_ID, PRESENTATION_MODERNIZE_TILE_ID}:
            return self._submit_presentation_plan(payload, config, profile)
        raise ValueError("Diese Werkstatt-Kachel ist noch nicht verfügbar.")

    def _submit_thesis(self, payload: dict, config: dict, profile: str) -> dict:
        tile_id = THESIS_TILE_ID
        (
            harness,
            harness_config,
            executable,
            alias,
            project_path,
        ) = self._harness_context(payload, config)

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
            route=harness,
            risk_level="medium",
            plan=[
                {"title": "Eingaben sicher übernehmen", "quality_gate": True},
                {"title": f"Gutachter-Agent mit {self._harness_name(harness)} ausführen"},
                {"title": "Ergebnis und Pflichtbestandteile prüfen", "quality_gate": True},
                {"title": "Abschlussbericht bereitstellen", "quality_gate": True},
            ],
            metadata={
                "tile_id": tile_id,
                "agent": "thesis-reviewer",
                "harness": harness,
                "model": self._selected_model(payload, harness, harness_config),
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
                "harness": harness,
                "harness_config": harness_config,
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

    def _submit_presentation_scaffold(
        self, payload: dict, config: dict, profile: str
    ) -> dict:
        default_harness = str(
            config.get("workbench", {}).get("default_harness") or "opencode"
        ).strip().casefold()
        project_config = config.get(
            default_harness if default_harness in {"opencode", "codex"} else "opencode",
            {},
        )
        alias, project_path = self._project_context(payload, project_config)
        output_path = self._project_member(
            project_path,
            payload.get("output_path"),
            label="Ausgabeordner",
            require_exists=False,
            allow_project_root=False,
        )
        if output_path.exists() and any(output_path.iterdir()):
            raise ValueError(
                "Der Ausgabeordner enthält bereits Dateien. Bitte einen neuen Ordner wählen."
            )
        template_root = self._presentation_template_root()
        if not template_root.is_dir():
            raise ValueError("Das Präsentationsgrundgerüst ist nicht installiert.")

        job = self.jobs.create_job(
            title="Präsentationsgrundgerüst anlegen",
            source="workbench",
            route="trinity",
            risk_level="low",
            plan=[
                {"title": "Projektpfad prüfen", "quality_gate": True},
                {"title": "Briefing und Vorlagen kopieren", "quality_gate": True},
            ],
            metadata={
                "tile_id": PRESENTATION_SCAFFOLD_TILE_ID,
                "agent": "html-praesentationswerkstatt",
                "harness": "trinity",
                "project": alias,
                "profile": str(profile or ""),
                "output_path": str(output_path.relative_to(project_path)),
            },
        )
        thread = threading.Thread(
            target=self._run_presentation_scaffold,
            kwargs={
                "job_id": job["job_id"],
                "template_root": template_root,
                "output_path": output_path,
            },
            daemon=True,
            name=f"trinity-workbench-{job['job_id'][-8:]}",
        )
        with self._lock:
            self._threads[job["job_id"]] = thread
        thread.start()
        return {"ok": True, "job": self.public_job(job["job_id"])}

    def _submit_presentation_plan(
        self, payload: dict, config: dict, profile: str
    ) -> dict:
        tile_id = str(payload.get("tile_id") or PRESENTATION_BUILD_TILE_ID).strip()
        presentation_mode = str(
            payload.get("presentation_mode")
            or (
                "modernize"
                if tile_id == PRESENTATION_MODERNIZE_TILE_ID
                else "new"
            )
        ).strip().casefold()
        if presentation_mode not in {"new", "modernize"}:
            raise ValueError("Bitte eine neue oder zu modernisierende Präsentation wählen.")
        source_deck_names = [
            Path(str(item.get("name") or "")).name
            for item in (payload.get("attachments") or [])
            if Path(str(item.get("name") or "")).suffix.casefold()
            in {".pptx", ".pdf"}
        ]
        if presentation_mode == "modernize" and len(source_deck_names) != 1:
            raise ValueError(
                "Zum Modernisieren wird genau eine vorhandene PPTX- oder "
                "PDF-Präsentation benötigt."
            )
        (
            harness,
            harness_config,
            executable,
            alias,
            project_path,
        ) = self._harness_context(payload, config)
        source_path = None
        if str(payload.get("source_path") or "").strip():
            source_path = self._project_member(
                project_path,
                payload.get("source_path"),
                label="Quellpfad",
                require_exists=True,
                allow_project_root=True,
            )
        title_input = str(payload.get("title") or "").strip()
        if not title_input and source_deck_names:
            title_input = Path(source_deck_names[0]).stem
        raw_output_path = str(payload.get("output_path") or "").strip()
        if not raw_output_path:
            raw_output_path = (
                "HTML-Präsentationen/"
                + (title_input or f"Neuer Entwurf {time.strftime('%Y-%m-%d_%H%M')}")
            )
        output_path = self._project_member(
            project_path,
            raw_output_path,
            label="Ausgabeordner",
            require_exists=False,
            allow_project_root=False,
        )
        if output_path.exists() and any(output_path.iterdir()):
            raise ValueError(
                "Der Ausgabeordner enthält bereits Dateien. Für eine neue "
                "Präsentation bitte einen neuen, sprechenden Ordner wählen."
            )

        title = title_input or output_path.name or "Neue Präsentation"
        outline = str(payload.get("outline") or "").strip()
        payload = {
            **payload,
            "title": title,
            "output_path": raw_output_path,
            "presentation_mode": presentation_mode,
        }
        duration = self._optional_int(payload.get("duration_minutes"), 1, 480)
        slide_count = self._optional_int(payload.get("slide_count"), 3, 100)

        provider = str(payload.get("image_provider") or "kie").strip().casefold()
        if provider != "kie":
            raise ValueError("Für diese Werkstatt ist derzeit nur Kie.ai freigegeben.")
        image_model = str(payload.get("image_model") or "").strip()
        if not image_model:
            image_model = PRESENTATION_IMAGE_MODELS[provider][0]["id"]
        if image_model not in {
            model["id"] for model in PRESENTATION_IMAGE_MODELS["kie"]
        }:
            raise ValueError("Bitte eines der freigegebenen Kie.ai-Modelle wählen.")

        job = self.jobs.create_job(
            title=(
                f"Präsentation modernisieren · {title}"
                if presentation_mode == "modernize"
                else f"HTML-Präsentation · {title}"
            ),
            source="workbench",
            route=harness,
            risk_level="medium",
            plan=[
                {"title": "Eingaben, Materialien und Pfade übernehmen", "quality_gate": True},
                {"title": "Recherche und Präsentationsplan erstellen", "quality_gate": True},
                {"title": "Plan durch Nutzer prüfen und freigeben", "quality_gate": True},
                {"title": "HTML-Präsentation und Medien bauen"},
                {"title": "Offline-, Quellen- und Qualitätsprüfung", "quality_gate": True},
            ],
            metadata={
                "tile_id": tile_id,
                "agent": "html-praesentationswerkstatt",
                "presentation_mode": presentation_mode,
                "harness": harness,
                "model": self._selected_model(payload, harness, harness_config),
                "project": alias,
                "profile": str(profile or ""),
                "title": title,
                "source_path": (
                    str(source_path.relative_to(project_path)) if source_path else ""
                ),
                "output_path": str(output_path.relative_to(project_path)),
                "image_provider": provider,
                "image_model": image_model,
            },
        )
        job_dir = self.upload_root / job["job_id"]
        staged = self._stage_presentation_attachments(
            job_dir, payload.get("attachments") or []
        )
        output_path.mkdir(parents=True, exist_ok=True)
        reference_dir = output_path / "reference-material"
        reference_dir.mkdir(parents=True, exist_ok=True)
        preserved = self._preserve_presentation_attachments(staged, reference_dir)
        request_record = {
            "schema_version": 1,
            "presentation_mode": presentation_mode,
            "title": title,
            "audience": str(payload.get("audience") or "").strip(),
            "purpose": str(payload.get("purpose") or "").strip(),
            "duration_minutes": duration,
            "slide_count": slide_count,
            "languages": list(payload.get("languages") or ["de"]),
            "outline": outline,
            "notes": str(payload.get("notes") or "").strip(),
            "project": alias,
            "source_path": str(source_path or ""),
            "output_path": str(output_path),
            "image_provider": provider,
            "image_model": image_model,
            "reference_files": [item["name"] for item in preserved],
            "source_deck": source_deck_names[0] if source_deck_names else "",
        }
        (output_path / "presentation-request.json").write_text(
            json.dumps(request_record, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        thread = threading.Thread(
            target=self._run_presentation_plan,
            kwargs={
                "job_id": job["job_id"],
                "job_dir": job_dir,
                "payload": payload,
                "harness": harness,
                "harness_config": harness_config,
                "executable": executable,
                "project_alias": alias,
                "project_path": project_path,
                "source_path": source_path,
                "output_path": output_path,
                "preserved": preserved,
                "provider": provider,
                "image_model": image_model,
                "config": config,
            },
            daemon=True,
            name=f"trinity-workbench-{job['job_id'][-8:]}",
        )
        with self._lock:
            self._threads[job["job_id"]] = thread
        thread.start()
        return {"ok": True, "job": self.public_job(job["job_id"])}

    def approve_presentation(
        self, payload: dict, config: dict, profile: str
    ) -> dict:
        if not isinstance(payload, dict):
            raise ValueError("Die Präsentationsfreigabe muss ein Objekt sein.")
        job_id = str(payload.get("job_id") or "").strip()
        job = self.jobs.get(job_id)
        if job["status"] != "WAITING_FOR_APPROVAL":
            raise ValueError("Dieser Auftrag wartet nicht auf eine Planfreigabe.")
        metadata = job.get("metadata") or {}
        if metadata.get("tile_id") not in {
            PRESENTATION_BUILD_TILE_ID,
            PRESENTATION_MODERNIZE_TILE_ID,
        }:
            raise ValueError("Die Freigabe gehört nicht zu einer HTML-Präsentation.")
        if str(metadata.get("profile") or "").upper() != str(profile or "").upper():
            raise PermissionError("Der Präsentationsauftrag gehört zu einem anderen Profil.")

        plan_text = str(payload.get("plan") or "").strip()
        if not plan_text:
            raise ValueError("Der freigegebene Präsentationsplan darf nicht leer sein.")
        if len(plan_text.encode("utf-8")) > 300_000:
            raise ValueError("Der Präsentationsplan ist ungewöhnlich groß.")

        harness = str(metadata.get("harness") or "opencode").strip().casefold()
        harness_config = config.get(harness, {})
        executable = self._find_harness_executable(harness)
        if not harness_config.get("enabled") or not executable:
            raise ValueError(
                f"{self._harness_name(harness)} ist für die Fortsetzung nicht verfügbar."
            )
        alias = str(metadata.get("project") or "")
        projects = self._configured_projects(harness_config)
        project_path = projects.get(alias)
        if project_path is None:
            raise ValueError("Der freigegebene Projektordner ist nicht mehr verfügbar.")
        output_path = self._project_member(
            project_path,
            metadata.get("output_path"),
            label="Ausgabeordner",
            require_exists=True,
            allow_project_root=False,
        )
        plan_path = output_path / "presentation-plan.md"
        plan_path.write_text(plan_text.rstrip() + "\n", encoding="utf-8")
        current = self.jobs.get(job_id)
        self.jobs.update_step(
            job_id,
            current["steps"][2]["step_id"],
            "SUCCEEDED",
            {"approval": "FREIGABE", "plan_path": str(plan_path)},
        )
        self.jobs.set_status(
            job_id,
            "RUNNING",
            "Der überarbeitete Plan ist freigegeben; die Präsentation wird gebaut.",
            {"approval": "FREIGABE"},
        )
        thread = threading.Thread(
            target=self._run_presentation_build,
            kwargs={
                "job_id": job_id,
                "harness": harness,
                "harness_config": harness_config,
                "executable": executable,
                "project_path": project_path,
                "output_path": output_path,
                "metadata": metadata,
                "config": config,
            },
            daemon=True,
            name=f"trinity-workbench-{job_id[-8:]}",
        )
        with self._lock:
            if job_id in self._threads:
                raise RuntimeError("Dieser Präsentationsauftrag läuft bereits.")
            self._threads[job_id] = thread
        thread.start()
        return {"ok": True, "job": self.public_job(job_id)}

    def public_jobs(self, limit: int = 30) -> list[dict]:
        jobs = self.jobs.list(limit=max(1, min(int(limit), 100)))
        compact = []
        for job in jobs:
            if job.get("source") != "workbench":
                continue
            public = self.public_job(job["job_id"])
            public["events"] = []
            public["steps"] = [
                {
                    "step_id": step["step_id"],
                    "position": step["position"],
                    "title": step["title"],
                    "quality_gate": step["quality_gate"],
                    "status": step["status"],
                    "details": {},
                }
                for step in public.get("steps", [])
            ]
            compact.append(public)
        return compact

    def cancel_job(self, job_id: str, profile: str) -> dict:
        """Cancel one profile-owned workbench job and stop its harness process."""

        job = self._profile_job(job_id, profile)
        if job["status"] in {"SUCCEEDED", "FAILED", "NEEDS_ESCALATION"}:
            raise ValueError("Dieser Auftrag ist bereits abgeschlossen.")
        if job["status"] == "CANCELLED":
            return {"ok": True, "job": self.public_job(job_id)}

        with self._lock:
            self._cancelled.add(job_id)
            process = self._processes.get(job_id)
        if process is not None:
            self._stop_process(process)

        current = self.jobs.get(job_id)
        for step in current.get("steps", []):
            if step["status"] in {"PENDING", "RUNNING"}:
                self.jobs.update_step(
                    job_id,
                    step["step_id"],
                    "SKIPPED",
                    {"cancelled_by_user": True},
                )
        self.jobs.set_status(
            job_id,
            "CANCELLED",
            "Der Auftrag wurde durch den Nutzer abgebrochen.",
            {"cancelled_by_user": True},
        )
        return {"ok": True, "job": self.public_job(job_id)}

    def delete_job(self, job_id: str, profile: str) -> dict:
        """Remove one terminal workbench record without deleting its output files."""

        self._profile_job(job_id, profile)
        self.jobs.delete(job_id)
        shutil.rmtree(self.upload_root / job_id, ignore_errors=True)
        with self._lock:
            self._cancelled.discard(job_id)
            self._threads.pop(job_id, None)
            self._processes.pop(job_id, None)
        return {"ok": True, "deleted_job_id": job_id}

    def _profile_job(self, job_id: str, profile: str) -> dict:
        clean_id = str(job_id or "").strip()
        if not clean_id:
            raise ValueError("Eine Job-ID wird benötigt.")
        job = self.jobs.get(clean_id)
        if job.get("source") != "workbench":
            raise PermissionError("Dieser Auftrag gehört nicht zur Werkstatt.")
        expected = str((job.get("metadata") or {}).get("profile") or "").upper()
        current = str(profile or "").upper()
        if expected and expected != current:
            raise PermissionError("Der Auftrag gehört zu einem anderen Profil.")
        return job

    def _job_cancelled(self, job_id: str) -> bool:
        with self._lock:
            return job_id in self._cancelled

    @staticmethod
    def _stop_process(process: subprocess.Popen) -> None:
        if process.poll() is not None:
            return
        try:
            if os.name == "nt":
                process.terminate()
            else:
                os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            try:
                if os.name == "nt":
                    process.kill()
                else:
                    os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                pass

    def secret_status(self, config: dict) -> dict:
        secrets = self._load_secrets(config)
        return {
            "ok": True,
            "kie_configured": bool(secrets.get("kie_ai")),
        }

    def save_secrets(self, payload: dict, config: dict) -> dict:
        if not isinstance(payload, dict):
            raise ValueError("API-Schlüssel müssen als Objekt übergeben werden.")
        secrets = self._load_secrets(config)
        for key in ("kie_ai",):
            if payload.get(f"clear_{key}"):
                secrets.pop(key, None)
                continue
            value = str(payload.get(key) or "").strip()
            if value:
                if len(value) > 1000:
                    raise ValueError("Ein API-Schlüssel ist ungewöhnlich lang.")
                secrets[key] = value
        self.secrets_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.secrets_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(secrets, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        try:
            temporary.chmod(0o600)
        except OSError:
            pass
        temporary.replace(self.secrets_path)
        try:
            self.secrets_path.chmod(0o600)
        except OSError:
            pass
        return self.secret_status(config)

    def public_job(self, job_id: str) -> dict:
        job = self.jobs.get(str(job_id or ""))
        events = []
        for event in job.get("events", []):
            details = dict(event.get("details") or {})
            details.pop("prompt", None)
            events.append({**event, "details": details})
        completed_steps = sum(
            step.get("status") in {"SUCCEEDED", "SKIPPED"}
            for step in job.get("steps", [])
        )
        current_step = next(
            (
                step
                for step in job.get("steps", [])
                if step.get("status") == "RUNNING"
            ),
            None,
        )
        total_steps = len(job.get("steps", []))
        progress_percent = (
            int((completed_steps / total_steps) * 100) if total_steps else 0
        )
        terminal = job.get("status") in {
            "SUCCEEDED",
            "FAILED",
            "NEEDS_ESCALATION",
            "CANCELLED",
        }
        elapsed_until = job.get("updated_at") if terminal else time.time()
        return {
            **job,
            "events": events,
            "progress": {
                "completed_steps": completed_steps,
                "total_steps": total_steps,
                "percent": progress_percent,
                "current_step": (
                    {
                        "position": current_step.get("position"),
                        "title": current_step.get("title"),
                    }
                    if current_step
                    else None
                ),
            },
            "elapsed_seconds": max(
                0, int(float(elapsed_until or 0) - float(job.get("created_at") or 0))
            ),
        }

    def _run_presentation_scaffold(
        self, *, job_id: str, template_root: Path, output_path: Path
    ) -> None:
        try:
            current = self.jobs.start(
                job_id, "Das Präsentationsgrundgerüst wird lokal angelegt."
            )
            self.jobs.update_step(
                job_id,
                current["steps"][0]["step_id"],
                "SUCCEEDED",
                {"output_path": str(output_path)},
            )
            self.jobs.update_step(
                job_id, current["steps"][1]["step_id"], "RUNNING"
            )
            if output_path.exists():
                output_path.mkdir(parents=True, exist_ok=True)
                shutil.copytree(template_root, output_path, dirs_exist_ok=True)
            else:
                shutil.copytree(template_root, output_path)
            readme = output_path / "README.md"
            readme.write_text(
                "# Präsentationsgrundgerüst\n\n"
                "Öffne `briefing.html`, fülle das visuelle Briefing aus und "
                "exportiere anschließend die Angaben oder nutze in Trinity die "
                "Kachel „HTML-Präsentation erstellen“.\n",
                encoding="utf-8",
            )
            if self._job_cancelled(job_id):
                raise WorkbenchJobCancelled(
                    "Der Werkstattauftrag wurde durch den Nutzer abgebrochen."
                )
            self.jobs.update_step(
                job_id,
                current["steps"][1]["step_id"],
                "SUCCEEDED",
                {
                    "summary": "Briefing und lokale Assets wurden vollständig kopiert.",
                    "briefing_path": str(output_path / "briefing.html"),
                },
            )
            self.jobs.complete(
                job_id,
                "Präsentationsgrundgerüst ist bereit.",
                {"summary": f"Öffne: {output_path / 'briefing.html'}"},
            )
        except WorkbenchJobCancelled:
            pass
        except Exception as exc:  # pylint: disable=broad-except
            self.jobs.fail(
                job_id,
                "Präsentationsgrundgerüst konnte nicht angelegt werden.",
                {"error": str(exc)[:4000]},
            )
        finally:
            with self._lock:
                self._threads.pop(job_id, None)

    def _run_presentation_plan(
        self,
        *,
        job_id: str,
        job_dir: Path,
        payload: dict,
        harness: str,
        harness_config: dict,
        executable: str,
        project_alias: str,
        project_path: Path,
        source_path: Optional[Path],
        output_path: Path,
        preserved: list[dict],
        provider: str,
        image_model: str,
        config: dict,
    ) -> None:
        try:
            current = self.jobs.start(
                job_id,
                (
                    "Präsentationsauftrag wurde an "
                    f"{self._harness_name(harness)} übergeben."
                ),
            )
            self.jobs.update_step(
                job_id,
                current["steps"][0]["step_id"],
                "SUCCEEDED",
                {
                    "project": project_alias,
                    "source_path": str(source_path or ""),
                    "output_path": str(output_path),
                    "files": [
                        {"name": item["name"], "sha256": item["sha256"]}
                        for item in preserved
                    ],
                },
            )
            self.jobs.update_step(
                job_id, current["steps"][1]["step_id"], "RUNNING"
            )
            prompt = self._presentation_plan_prompt(
                payload=payload,
                project_alias=project_alias,
                source_path=source_path,
                output_path=output_path,
                preserved=preserved,
                provider=provider,
                image_model=image_model,
                secret_status=self.secret_status(config),
            )
            timeout = self._bounded_int(
                harness_config.get("timeout_seconds"), 1800, 900, 7200
            )
            output = self._run_harness_with_heartbeat(
                job_id=job_id,
                harness=harness,
                phase="Recherche und Folienplan",
                runner=lambda: self._run_harness(
                    job_id=job_id,
                    harness=harness,
                    executable=executable,
                    project_path=project_path,
                    prompt=prompt,
                    attachments=[item["path"] for item in preserved],
                    model=self._selected_model(payload, harness, harness_config),
                    agent="html-praesentationswerkstatt",
                    harness_config=harness_config,
                    timeout=timeout,
                    extra_env=self._presentation_environment(
                        config, provider, image_model, output_path
                    ),
                ),
            )
            plan_path = output_path / "presentation-plan.md"
            if plan_path.is_file():
                plan_text = plan_path.read_text(encoding="utf-8").strip()
            else:
                plan_text = output.strip()
                if plan_text:
                    plan_path.write_text(plan_text.rstrip() + "\n", encoding="utf-8")
            if not plan_text:
                raise RuntimeError(
                    f"{self._harness_name(harness)} hat keinen "
                    "presentation-plan.md und keinen Plantext geliefert."
                )
            self.jobs.update_step(
                job_id,
                current["steps"][1]["step_id"],
                "SUCCEEDED",
                {"summary": output[-4000:], "plan_path": str(plan_path)},
            )
            self.jobs.set_status(
                job_id,
                "WAITING_FOR_APPROVAL",
                "Der Präsentationsplan ist bereit und wartet auf deine Anmerkungen.",
                {
                    "plan": plan_text[:300_000],
                    "plan_path": str(plan_path),
                    "approval_word": "FREIGABE",
                },
            )
        except WorkbenchJobCancelled:
            pass
        except Exception as exc:  # pylint: disable=broad-except
            try:
                self.jobs.fail(
                    job_id,
                    "Präsentationsplanung fehlgeschlagen.",
                    {"error": str(exc)[:4000]},
                )
            except ValueError:
                pass
        finally:
            shutil.rmtree(job_dir, ignore_errors=True)
            with self._lock:
                self._threads.pop(job_id, None)

    def _run_presentation_build(
        self,
        *,
        job_id: str,
        harness: str,
        harness_config: dict,
        executable: str,
        project_path: Path,
        output_path: Path,
        metadata: dict,
        config: dict,
    ) -> None:
        try:
            current = self.jobs.get(job_id)
            self.jobs.update_step(
                job_id, current["steps"][3]["step_id"], "RUNNING"
            )
            prompt = self._presentation_build_prompt(
                output_path=output_path,
                metadata=metadata,
                secret_status=self.secret_status(config),
            )
            timeout = self._bounded_int(
                harness_config.get("timeout_seconds"), 3600, 1800, 7200
            )
            output = self._run_harness_with_heartbeat(
                job_id=job_id,
                harness=harness,
                phase="HTML-Präsentation, Medien und Qualitätsprüfung",
                runner=lambda: self._run_harness(
                    job_id=job_id,
                    harness=harness,
                    executable=executable,
                    project_path=project_path,
                    prompt=prompt,
                    attachments=[],
                    model=str(
                        metadata.get("model")
                        or harness_config.get("model")
                        or ("gpt-5.6-sol" if harness == "codex" else "")
                    ).strip(),
                    agent="html-praesentationswerkstatt",
                    harness_config=harness_config,
                    timeout=timeout,
                    extra_env=self._presentation_environment(
                        config,
                        str(metadata.get("image_provider") or "kie"),
                        str(
                            metadata.get("image_model")
                            or "gpt-image-2-text-to-image"
                        ),
                        output_path,
                    ),
                ),
            )
            self.jobs.update_step(
                job_id,
                current["steps"][3]["step_id"],
                "SUCCEEDED",
                {"summary": output[-4000:]},
            )
            self.jobs.update_step(
                job_id, current["steps"][4]["step_id"], "RUNNING"
            )
            missing = [
                name
                for name in ("presentation.html", "review.html")
                if not (output_path / name).is_file()
            ]
            if missing:
                raise RuntimeError(
                    "Pflichtdateien fehlen nach dem Agentenlauf: " + ", ".join(missing)
                )
            self.jobs.update_step(
                job_id,
                current["steps"][4]["step_id"],
                "SUCCEEDED",
                {
                    "quality_gate": (
                        "presentation.html und review.html sind vorhanden. "
                        "Die fachliche und visuelle Endfreigabe bleibt beim Nutzer."
                    ),
                    "presentation_path": str(output_path / "presentation.html"),
                    "review_path": str(output_path / "review.html"),
                },
            )
            self.jobs.complete(
                job_id,
                "HTML-Präsentation abgeschlossen.",
                {
                    "summary": output[-8000:],
                    "presentation_path": str(output_path / "presentation.html"),
                    "review_path": str(output_path / "review.html"),
                },
            )
        except WorkbenchJobCancelled:
            pass
        except Exception as exc:  # pylint: disable=broad-except
            try:
                current = self.jobs.get(job_id)
                for step in current["steps"]:
                    if step["status"] == "RUNNING":
                        self.jobs.update_step(
                            job_id,
                            step["step_id"],
                            "FAILED",
                            {"error": str(exc)[:4000]},
                        )
                self.jobs.fail(
                    job_id,
                    "Präsentationserstellung fehlgeschlagen.",
                    {"error": str(exc)[:4000]},
                )
            except ValueError:
                pass
        finally:
            with self._lock:
                self._threads.pop(job_id, None)

    def _stage_presentation_attachments(
        self, job_dir: Path, attachments: list[dict]
    ) -> list[dict]:
        if not isinstance(attachments, list):
            raise ValueError("Präsentationsanlagen müssen eine Liste sein.")
        job_dir.mkdir(parents=True, exist_ok=False)
        staged = []
        total = 0
        try:
            for index, item in enumerate(attachments):
                name = Path(
                    str(item.get("name") or f"referenz-{index + 1}")
                ).name
                suffix = Path(name).suffix.casefold()
                if suffix not in PRESENTATION_ALLOWED_SUFFIXES:
                    raise ValueError(
                        f"{name} ist kein unterstütztes Präsentationsmaterial."
                    )
                try:
                    data = base64.b64decode(
                        str(item.get("data_base64") or ""), validate=True
                    )
                except (ValueError, TypeError) as exc:
                    raise ValueError(f"{name} konnte nicht gelesen werden.") from exc
                total += len(data)
                if not data or len(data) > MAX_UPLOAD_BYTES:
                    raise ValueError(f"{name} ist leer oder größer als 30 MB.")
                if total > MAX_PRESENTATION_UPLOAD_BYTES:
                    raise ValueError("Die Präsentationsanlagen sind zusammen größer als 60 MB.")
                target = job_dir / f"{index + 1:02d}_{name}"
                target.write_bytes(data)
                staged.append(
                    {
                        "name": name,
                        "path": target,
                        "sha256": hashlib.sha256(data).hexdigest(),
                    }
                )
        except Exception:
            shutil.rmtree(job_dir, ignore_errors=True)
            raise
        return staged

    @staticmethod
    def _preserve_presentation_attachments(
        staged: list[dict], reference_dir: Path
    ) -> list[dict]:
        preserved = []
        for index, item in enumerate(staged, start=1):
            target = reference_dir / item["name"]
            if target.exists():
                target = reference_dir / f"{index:02d}_{item['name']}"
            shutil.copy2(item["path"], target)
            preserved.append({**item, "path": target})
        return preserved

    def _load_secrets(self, config: dict) -> dict:
        try:
            data = json.loads(self.secrets_path.read_text(encoding="utf-8"))
            secrets = data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            secrets = {}
        apis = config.get("apis", {}) if isinstance(config.get("apis"), dict) else {}
        if not secrets.get("kie_ai") and apis.get("kie_ai"):
            secrets["kie_ai"] = str(apis["kie_ai"])
        if not secrets.get("fal_ai") and apis.get("fal_ai"):
            secrets["fal_ai"] = str(apis["fal_ai"])
        return secrets

    def _presentation_environment(
        self,
        config: dict,
        provider: str,
        image_model: str,
        output_path: Path,
    ) -> dict:
        secrets = self._load_secrets(config)
        environment = {
            "TRINITY_IMAGE_PROVIDER": provider,
            "TRINITY_IMAGE_MODEL": image_model,
            "TRINITY_PRESENTATION_OUTPUT": str(output_path),
            "TRINITY_PRESENTATION_TOOLKIT": str(self.presentation_resources),
            "TRINITY_PRESENTATION_IMAGE_HELPER": str(
                self.home / "scripts" / "presentation_image.py"
            ),
        }
        if secrets.get("kie_ai"):
            environment["KIE_API_KEY"] = str(secrets["kie_ai"])
        return environment

    def _presentation_template_root(self) -> Path:
        return self.presentation_resources / "template"

    @staticmethod
    def _harness_name(harness: str) -> str:
        return {
            "codex": "Codex / ChatGPT",
            "opencode": "OpenCode",
        }.get(str(harness or "").casefold(), str(harness or "Agent"))

    @staticmethod
    def _find_harness_executable(harness: str) -> Optional[str]:
        if harness == "codex":
            return find_codex_executable()
        if harness == "opencode":
            return find_opencode_executable()
        return None

    @staticmethod
    def _selected_model(payload: dict, harness: str, harness_config: dict) -> str:
        model = str(
            payload.get("model")
            or harness_config.get("model")
            or ("gpt-5.6-sol" if harness == "codex" else "")
        ).strip()
        if harness == "codex" and model not in CODEX_MODEL_IDS:
            raise ValueError("Bitte eines der freigegebenen Codex-/ChatGPT-Modelle wählen.")
        return model

    def _harness_context(
        self, payload: dict, config: dict
    ) -> tuple[str, dict, str, str, Path]:
        harness = str(
            payload.get("harness")
            or config.get("workbench", {}).get("default_harness")
            or "opencode"
        ).strip().casefold()
        if harness not in {"opencode", "codex"}:
            raise ValueError("Bitte OpenCode oder Codex / ChatGPT wählen.")
        harness_config = config.get(harness, {})
        if not harness_config.get("enabled"):
            raise ValueError(
                f"{self._harness_name(harness)} ist in Trinity noch nicht aktiviert."
            )
        executable = self._find_harness_executable(harness)
        if not executable:
            raise ValueError(
                f"{self._harness_name(harness)} wurde auf diesem Rechner nicht gefunden."
            )
        alias, project_path = self._project_context(payload, harness_config)
        return harness, harness_config, executable, alias, project_path

    @staticmethod
    def _project_context(payload: dict, config: dict) -> tuple[str, Path]:
        projects = WorkbenchManager._configured_projects(config)
        alias = str(
            payload.get("project")
            or config.get("default_project")
            or (next(iter(projects)) if len(projects) == 1 else "")
        ).strip()
        project_path = projects.get(alias)
        if project_path is None:
            raise ValueError(
                "Bitte einen in Trinity freigegebenen Projektordner wählen."
            )
        return alias, project_path

    @staticmethod
    def _project_member(
        project_path: Path,
        raw_path,
        *,
        label: str,
        require_exists: bool,
        allow_project_root: bool,
    ) -> Path:
        value = str(raw_path or "").strip()
        if not value:
            raise ValueError(f"{label} darf nicht leer sein.")
        candidate = Path(os.path.expandvars(os.path.expanduser(value)))
        if not candidate.is_absolute():
            candidate = project_path / candidate
        resolved = candidate.resolve()
        try:
            resolved.relative_to(project_path)
        except ValueError as exc:
            raise ValueError(
                f"{label} muss innerhalb des ausgewählten Projektordners liegen."
            ) from exc
        if not allow_project_root and resolved == project_path:
            raise ValueError(f"{label} muss ein eigener Unterordner sein.")
        if require_exists and not resolved.exists():
            raise ValueError(f"{label} wurde nicht gefunden: {resolved}")
        return resolved

    @staticmethod
    def _optional_int(value, minimum: int, maximum: int) -> Optional[int]:
        if value in {None, ""}:
            return None
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("Dauer und Folienzahl müssen ganze Zahlen sein.") from exc
        if parsed < minimum or parsed > maximum:
            raise ValueError(f"Der Wert muss zwischen {minimum} und {maximum} liegen.")
        return parsed

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
        harness: str,
        harness_config: dict,
        executable: str,
        project_alias: str,
        project_path: Path,
        review_type: str,
    ) -> None:
        try:
            current = self.jobs.start(
                job_id,
                f"Gutachter-Auftrag wurde an {self._harness_name(harness)} übergeben.",
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
            timeout = self._bounded_int(
                harness_config.get("timeout_seconds"), 1800, 900, 7200
            )
            output = self._run_harness_with_heartbeat(
                job_id=job_id,
                harness=harness,
                phase="Prüfung und Gutachtenentwurf",
                runner=lambda: self._run_harness(
                    job_id=job_id,
                    harness=harness,
                    executable=executable,
                    project_path=project_path,
                    prompt=prompt,
                    attachments=[item["path"] for item in staged],
                    model=self._selected_model(payload, harness, harness_config),
                    agent="thesis-reviewer",
                    harness_config=harness_config,
                    timeout=timeout,
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
                        f"{self._harness_name(harness)} hat einen Abschlussbericht geliefert. "
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
        except WorkbenchJobCancelled:
            pass
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

    def _presentation_plan_prompt(
        self,
        *,
        payload: dict,
        project_alias: str,
        source_path: Optional[Path],
        output_path: Path,
        preserved: list[dict],
        provider: str,
        image_model: str,
        secret_status: dict,
    ) -> str:
        skill_path = (
            Path.home()
            / ".agents"
            / "skills"
            / "html-praesentationswerkstatt"
            / "SKILL.md"
        )
        contract_path = skill_path.parent / "references" / "ARBEITSVERTRAG.md"
        reference_lines = "\n".join(
            f"- {item['name']}: {item['path']}" for item in preserved
        ) or "- keine hochgeladenen Dateien"
        languages = ", ".join(payload.get("languages") or ["de"])
        duration = payload.get("duration_minutes") or "(nicht vorgegeben)"
        slide_count = payload.get("slide_count") or "(nicht vorgegeben)"
        provider_ready = secret_status["kie_configured"]
        outline = str(payload.get("outline") or "").strip()
        presentation_mode = str(
            payload.get("presentation_mode") or "new"
        ).strip().casefold()
        source_decks = [
            item
            for item in preserved
            if Path(item["name"]).suffix.casefold() in {".pptx", ".pdf"}
        ]
        modernization_contract = ""
        if presentation_mode == "modernize":
            source_deck = source_decks[0]
            modernization_contract = f"""
Dies ist eine Modernisierung einer vorhandenen Präsentation.
Verbindliche Ausgangspräsentation: {source_deck["path"]}

Analysiere die Ausgangspräsentation vollständig, nicht nur einzelne Vorschauseiten.
Erfasse Reihenfolge, Titel, Kernaussagen, Sprechernotizen soweit zugänglich,
Schaubilder, Bilder, Tabellen und wiederkehrende Gestaltungsmuster. Bewahre das
Original unverändert unter `reference-material`.

Erstelle zusätzlich:
- `source-deck-analysis.md` mit einer vollständigen Folie-für-Folie-Analyse,
- `source-media-inventory.json` mit Herkunft, Foliennummer, Dateityp,
  Wiederverwendbarkeit und geplanter Verwendung jedes extrahierbaren Mediums.

Der Präsentationsplan muss jede Ausgangsfolie einer oder mehreren neuen stabilen
Folien-IDs zuordnen und die Entscheidung `behalten`, `überarbeiten`, `teilen`,
`zusammenführen` oder `entfernen` begründen. Übernimm brauchbare Schaubilder und
Bilder. Textlastige, veraltete oder technisch ungeeignete Darstellungen werden
als sauberes HTML/CSS/SVG-Schaubild oder – nur nach Planfreigabe – als neues Bild
rekonstruiert. Nichts darf verzerrt, abgeschnitten oder ohne Herkunftsnachweis
übernommen werden. Die zusätzlichen Änderungswünsche des Nutzers haben Vorrang.
"""
        return f"""Führe den installierten Agenten `html-praesentationswerkstatt` aus.

Dies ist ausschließlich Phase A/B: Recherche, Briefing-Auswertung und
`presentation-plan.md`. Baue noch KEINE Präsentation. Das Freigabewort wurde
noch nicht erteilt.

Verbindliche Agentenanweisung: {skill_path}
Verbindlicher Arbeitsvertrag: {contract_path}
Vollständiger lokaler Vorlagenbaukasten: {self.presentation_resources}
Freigegebenes Projekt: {project_alias}
Zusätzlicher Quellpfad: {source_path or "(keiner)"}
Neuer Präsentationsordner: {output_path}

Titel: {str(payload.get("title") or "").strip()}
Zielgruppe: {str(payload.get("audience") or "").strip() or "(offen)"}
Ziel und Anlass: {str(payload.get("purpose") or "").strip() or "(offen)"}
Vortragsdauer: {duration} Minuten
Gewünschte Folienzahl: {slide_count}
Sprachen: {languages}
Arbeitsmodus: {presentation_mode}

{modernization_contract}

Grobstruktur und Kernideen:
{outline or "(nicht vorgegeben – entwickle selbst eine sinnvolle Grobstruktur)"}

Zusätzliche Hinweise:
{str(payload.get("notes") or "").strip() or "(keine)"}

Unverändert übernommene Referenzmaterialien:
{reference_lines}

Bildplanung:
- bevorzugter Provider: {provider}
- bevorzugtes Modell: {image_model}
- API-Schlüssel für den bevorzugten Provider vorhanden: {str(provider_ready).lower()}

Die Schlüssel selbst dürfen niemals ausgegeben, in Dateien geschrieben oder in
die Präsentation übernommen werden. Plane nur tatsächlich verfügbare
Bildgenerierung ein. Wenn ein Schlüssel fehlt, kennzeichne das im Plan und plane
vorhandene Bilder, HTML/CSS-Schaubilder oder eine spätere manuelle Ergänzung.

Wenn Titel, Zielgruppe, Dauer, Folienzahl, Materialien oder Grobstruktur nicht
vorgegeben sind, stelle keine Rückfrage und brich nicht ab. Entwickle stattdessen
eine belastbare professionelle Ausgangsidee, kennzeichne deine Annahmen sichtbar
und mache sie im anschließend bearbeitbaren Plan leicht änderbar.

Erstelle nach Recherche und einer Gap-/Gegenprüfung im
Ordner {output_path} die Datei `presentation-plan.md`. Der Plan muss je Folie
eine stabile Folien-ID, Kernaussage, Quellenbedarf, Visualisierungsidee,
Interaktion, Zeitbudget und beabsichtigte Wirkung enthalten. Gib den Plan
zusätzlich vollständig in deiner Abschlussantwort aus und stoppe dann. Warte auf
das exakte Wort FREIGABE.
"""

    def _presentation_build_prompt(
        self, *, output_path: Path, metadata: dict, secret_status: dict
    ) -> str:
        skill_path = (
            Path.home()
            / ".agents"
            / "skills"
            / "html-praesentationswerkstatt"
            / "SKILL.md"
        )
        provider = str(metadata.get("image_provider") or "kie")
        provider_ready = secret_status["kie_configured"]
        modernization_contract = ""
        if str(metadata.get("presentation_mode") or "new") == "modernize":
            modernization_contract = f"""
Dies ist die freigegebene Modernisierung einer vorhandenen Präsentation.
Nutze `source-deck-analysis.md` und `source-media-inventory.json` im Ordner
{output_path}. Übernommene Bilder und Schaubilder müssen vollständig sichtbar,
unverzerrt und im Medienmanifest auf ihre Ausgangsfolie zurückführbar sein.
Rekonstruiere ungeeignete Darstellungen nach dem freigegebenen Plan als
HTML/CSS/SVG oder über die freigegebene Bildbrücke.
"""
        return f"""FREIGABE

Setze jetzt den vom Nutzer überarbeiteten und ausdrücklich freigegebenen Plan
vollständig mit dem installierten Agenten `html-praesentationswerkstatt` um.

Verbindliche Agentenanweisung: {skill_path}
Vollständiger lokaler Vorlagen- und Review-Baukasten:
{self.presentation_resources}
Präsentationsordner: {output_path}
Freigegebener Plan: {output_path / "presentation-plan.md"}
Anfrageprotokoll: {output_path / "presentation-request.json"}
Referenzmaterial: {output_path / "reference-material"}

{modernization_contract}

Bildkonfiguration:
- bevorzugter Provider: {provider}
- bevorzugtes Modell: {metadata.get("image_model") or "gpt-image-2-text-to-image"}
- bevorzugter Schlüssel vorhanden: {str(provider_ready).lower()}

Der Provider-Schlüssel steht nur als KIE_API_KEY in der Prozessumgebung.
Gib ihn niemals aus und schreibe ihn niemals in Dateien.
Nutze für eine tatsächlich freigegebene Bildgenerierung ausschließlich die
serverseitige Brücke in `TRINITY_PRESENTATION_IMAGE_HELPER`. Übergib den Prompt
über `--prompt-file`, den Provider über `--provider`, das Modell über `--model`
und den lokalen Zielpfad über `--output`. Übergib niemals einen Schlüssel als
Befehlsargument. Nutze Kie.ai nur, wenn der Schlüssel tatsächlich vorhanden
ist. Schlägt eine Bildgenerierung fehl, verwende ein lokales HTML/CSS-Schaubild
oder kennzeichne die spätere Medienergänzung im Review.

Erstelle alle im Arbeitsvertrag geforderten lokalen Dateien einschließlich
`presentation.html`, sprachspezifischer Fassungen, `review.html`,
`review-assets/`, Quellenübersicht, Medienmanifest und Druckansicht. Verwende
keine CDNs und keine zwingenden Netzwerkanfragen in der fertigen Präsentation.
Führe Review und Qualitätsprüfung aus. Veröffentliche nichts und überschreibe
keine anderen Präsentationsordner. Antworte abschließend auf Deutsch mit den
erzeugten Pfaden, dem Qualitätsstatus und noch offenen fachlichen Freigaben.
"""

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

    def _run_harness(
        self,
        *,
        job_id: str,
        harness: str,
        executable: str,
        project_path: Path,
        prompt: str,
        attachments: list[Path],
        model: str,
        agent: str,
        harness_config: dict,
        timeout: int,
        extra_env: Optional[dict] = None,
    ) -> str:
        if harness == "codex":
            return self._run_codex(
                job_id=job_id,
                executable=executable,
                project_path=project_path,
                prompt=prompt,
                attachments=attachments,
                model=model or "gpt-5.6-sol",
                sandbox=str(
                    harness_config.get("sandbox") or "workspace-write"
                ).strip(),
                ephemeral=bool(harness_config.get("ephemeral", True)),
                timeout=timeout,
                extra_env=extra_env,
            )
        if harness == "opencode":
            return self._run_opencode(
                job_id=job_id,
                executable=executable,
                project_path=project_path,
                prompt=prompt,
                attachments=attachments,
                model=model,
                agent=agent,
                server_url=str(harness_config.get("server_url") or "").strip(),
                timeout=timeout,
                extra_env=extra_env,
            )
        raise ValueError("Unbekanntes ausführendes System.")

    def _run_harness_with_heartbeat(
        self, *, job_id: str, harness: str, phase: str, runner
    ) -> str:
        result: dict[str, str] = {}
        errors: list[BaseException] = []

        def execute():
            try:
                result["output"] = runner()
            except BaseException as exc:  # pylint: disable=broad-except
                errors.append(exc)

        worker = threading.Thread(
            target=execute,
            daemon=True,
            name=f"trinity-harness-{job_id[-8:]}",
        )
        started = time.monotonic()
        worker.start()
        while worker.is_alive():
            worker.join(20)
            if not worker.is_alive():
                break
            if self._job_cancelled(job_id):
                worker.join(2)
                raise WorkbenchJobCancelled(
                    "Der Werkstattauftrag wurde durch den Nutzer abgebrochen."
                )
            elapsed = int(time.monotonic() - started)
            try:
                self.jobs.set_status(
                    job_id,
                    "RUNNING",
                    (
                        f"{self._harness_name(harness)} arbeitet weiter an „{phase}“ "
                        f"· bisher {elapsed // 60} min {elapsed % 60:02d} s."
                    ),
                    {
                        "heartbeat": True,
                        "phase": phase,
                        "elapsed_seconds": elapsed,
                    },
                )
            except ValueError:
                if self._job_cancelled(job_id):
                    raise WorkbenchJobCancelled(
                        "Der Werkstattauftrag wurde durch den Nutzer abgebrochen."
                    )
                raise
        if self._job_cancelled(job_id):
            raise WorkbenchJobCancelled(
                "Der Werkstattauftrag wurde durch den Nutzer abgebrochen."
            )
        if errors:
            raise errors[0]
        return result.get("output", "")

    def _run_codex(
        self,
        *,
        job_id: str = "",
        executable: str,
        project_path: Path,
        prompt: str,
        attachments: Optional[list[Path]] = None,
        model: str,
        sandbox: str,
        ephemeral: bool,
        timeout: int,
        extra_env: Optional[dict] = None,
    ) -> str:
        command = [
            executable,
            "exec",
            "--skip-git-repo-check",
            "--sandbox",
            sandbox if sandbox in {"read-only", "workspace-write"} else "workspace-write",
            "--cd",
            str(project_path),
        ]
        attachment_dirs = sorted(
            {
                str(Path(attachment).resolve().parent)
                for attachment in (attachments or [])
            }
        )
        for directory in attachment_dirs:
            command.extend(["--add-dir", directory])
        command.extend(["--model", model or "gpt-5.6-sol"])
        if ephemeral:
            command.append("--ephemeral")
        command.append("-")
        creation_flags = (
            getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        )
        use_shell = os.name == "nt" and str(executable).casefold().endswith(
            (".cmd", ".bat")
        )
        run_command = subprocess.list2cmdline(command) if use_shell else command
        try:
            completed = self._execute_process(
                run_command,
                job_id=job_id,
                input_text=prompt,
                timeout=timeout,
                shell=use_shell,
                cwd=project_path,
                env={
                    **os.environ,
                    "NO_COLOR": "1",
                    **{
                        str(key): str(value)
                        for key, value in (extra_env or {}).items()
                        if value is not None
                    },
                },
                creation_flags=creation_flags,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(
                "Codex / ChatGPT hat das Zeitlimit von "
                f"{max(1, timeout // 60)} Minuten erreicht. "
                "Der Auftrag wurde sicher beendet und kann erneut gestartet werden."
            ) from exc
        if completed.returncode != 0:
            details = (completed.stderr or completed.stdout or "").strip()
            raise OSError(
                "Codex / ChatGPT wurde mit Fehlercode "
                f"{completed.returncode} beendet: {details[-2500:]}"
            )
        return (completed.stdout or "").strip()

    def _run_opencode(
        self,
        *,
        job_id: str = "",
        executable: str,
        project_path: Path,
        prompt: str,
        attachments: list[Path],
        model: str,
        agent: str,
        server_url: str,
        timeout: int,
        extra_env: Optional[dict] = None,
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
        try:
            completed = self._execute_process(
                run_command,
                job_id=job_id,
                input_text=None,
                timeout=timeout,
                shell=use_shell,
                cwd=project_path,
                env={
                    **os.environ,
                    "NO_COLOR": "1",
                    **{
                        str(key): str(value)
                        for key, value in (extra_env or {}).items()
                        if value is not None
                    },
                },
                creation_flags=creation_flags,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(
                "OpenCode hat das Zeitlimit von "
                f"{max(1, timeout // 60)} Minuten erreicht. "
                "Der Auftrag wurde sicher beendet und kann erneut gestartet werden."
            ) from exc
        if completed.returncode != 0:
            details = (completed.stderr or completed.stdout or "").strip()
            raise OSError(
                f"OpenCode wurde mit Fehlercode {completed.returncode} beendet: "
                f"{details[-2500:]}"
            )
        return (completed.stdout or "").strip()

    def _execute_process(
        self,
        command,
        *,
        job_id: str,
        input_text: Optional[str],
        timeout: int,
        shell: bool,
        cwd: Path,
        env: dict,
        creation_flags: int,
    ) -> subprocess.CompletedProcess:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE if input_text is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=shell,
            cwd=str(cwd),
            env=env,
            creationflags=creation_flags,
            start_new_session=os.name != "nt",
        )
        if job_id:
            with self._lock:
                if job_id in self._cancelled:
                    self._stop_process(process)
                    raise WorkbenchJobCancelled(
                        "Der Werkstattauftrag wurde durch den Nutzer abgebrochen."
                    )
                self._processes[job_id] = process
        try:
            stdout, stderr = process.communicate(input=input_text, timeout=timeout)
        except subprocess.TimeoutExpired:
            self._stop_process(process)
            stdout, stderr = process.communicate()
            raise
        finally:
            if job_id:
                with self._lock:
                    if self._processes.get(job_id) is process:
                        self._processes.pop(job_id, None)
        return subprocess.CompletedProcess(
            command,
            process.returncode,
            stdout=stdout,
            stderr=stderr,
        )

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

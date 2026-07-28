import base64
import os
import subprocess
import time
from pathlib import Path

import pytest

import workbench
from configuration import default_config
from workbench import WorkbenchManager


def test_catalog_exposes_codex_and_opencode_with_separate_models(monkeypatch, tmp_path):
    project = tmp_path / "Lehre"
    project.mkdir()
    manager = WorkbenchManager(tmp_path)
    config = default_config("Linux")
    config["opencode"].update(
        {
            "enabled": True,
            "projects": {"Lehre": str(project)},
            "default_project": "Lehre",
        }
    )
    config["codex"].update(
        {
            "enabled": True,
            "projects": {"Lehre": str(project)},
            "default_project": "Lehre",
        }
    )
    monkeypatch.setattr(workbench, "find_opencode_executable", lambda: "/bin/opencode")
    monkeypatch.setattr(workbench, "find_codex_executable", lambda: "/bin/codex")
    monkeypatch.setattr(manager, "_opencode_models", lambda _config: [])

    catalog = manager.catalog(config, "BIZ")

    assert catalog["profile"] == "BIZ"
    assert catalog["harnesses"][0]["id"] == "opencode"
    assert catalog["harnesses"][0]["available"] is True
    assert catalog["harnesses"][1]["id"] == "codex"
    assert catalog["harnesses"][1]["available"] is True
    assert catalog["models_by_harness"]["codex"][0]["id"] == "gpt-5.6-sol"
    assert catalog["models_by_harness"]["codex"][1]["id"] == "gpt-5.6-terra"
    assert catalog["projects"][0]["name"] == "Lehre"
    assert catalog["categories"][0]["name"] == "Präsentationen, Papers und Lehrbücher"
    assert catalog["categories"][1]["name"] == "Begutachtungen und Prüfungen"
    assert catalog["categories"][2]["name"] == "Medienerstellung"
    assert catalog["categories"][3]["name"] == "Romanerstellung"
    assert catalog["categories"][1]["tiles"][0]["id"] == "thesis-reviewer"
    assert catalog["categories"][1]["tiles"][0]["available"] is True
    presentation_tiles = catalog["categories"][0]["tiles"]
    assert [tile["id"] for tile in presentation_tiles[:3]] == [
        "html-presentation-workshop",
        "html-presentation-modernize",
        "html-presentation-scaffold",
    ]
    assert presentation_tiles[0]["available"] is True
    assert presentation_tiles[1]["available"] is True
    assert presentation_tiles[3]["title"] == "Lehrbuch erstellen"
    assert presentation_tiles[3]["available"] is False
    assert catalog["presentation"]["default_image_provider"] == "kie"
    assert [
        model["id"]
        for model in catalog["presentation"]["image_providers"][0]["models"]
    ] == [
        "gpt-image-2-text-to-image",
        "nano-banana-2-lite",
        "flux-2/pro-text-to-image",
    ]
    assert len(catalog["presentation"]["image_providers"]) == 1


@pytest.mark.parametrize("profile", ["BIZ", "PRIVAT", "TEST"])
def test_thesis_tile_is_available_in_every_profile(tmp_path, profile):
    manager = WorkbenchManager(tmp_path)
    catalog = manager.catalog(default_config("Linux"), profile)

    tile = catalog["categories"][1]["tiles"][0]
    assert catalog["profile"] == profile
    assert tile["available"] is True
    assert tile["status"] == "bereit"
    assert tile["profiles"] == ["BIZ", "PRIVAT", "TEST"]

    with pytest.raises(ValueError, match="OpenCode"):
        manager.submit(
            {"tile_id": "thesis-reviewer", "harness": "opencode"},
            default_config("Linux"),
            profile,
        )


def test_workbench_stages_only_named_pdf_inputs(tmp_path):
    manager = WorkbenchManager(tmp_path)
    staged = manager._stage_attachments(
        tmp_path / "memory" / "workbench_uploads" / "job_test",
        [
            {
                "role": "thesis",
                "name": "../Thesis.pdf",
                "data_base64": base64.b64encode(b"%PDF-test").decode(),
            }
        ],
    )

    assert staged[0]["name"] == "Thesis.pdf"
    assert staged[0]["path"].parent.name == "job_test"
    assert staged[0]["sha256"]


def test_workbench_rejects_non_pdf_input(tmp_path):
    manager = WorkbenchManager(tmp_path)

    with pytest.raises(ValueError, match="PDF"):
        manager._stage_attachments(
            tmp_path / "memory" / "workbench_uploads" / "job_test",
            [
                {
                    "role": "thesis",
                    "name": "Thesis.txt",
                    "data_base64": base64.b64encode(b"text").decode(),
                }
            ],
        )


def test_workbench_job_can_be_cancelled_then_deleted(tmp_path):
    manager = WorkbenchManager(tmp_path)
    job = manager.jobs.create_job(
        "Präsentation erstellen",
        source="workbench",
        metadata={"profile": "PRIVAT"},
        plan=[{"title": "Planen"}, {"title": "Bauen"}],
    )
    manager.jobs.start(job["job_id"])
    manager.jobs.update_step(
        job["job_id"], job["steps"][0]["step_id"], "RUNNING"
    )

    cancelled = manager.cancel_job(job["job_id"], "PRIVAT")

    assert cancelled["job"]["status"] == "CANCELLED"
    assert all(
        step["status"] == "SKIPPED" for step in cancelled["job"]["steps"]
    )
    deleted = manager.delete_job(job["job_id"], "PRIVAT")
    assert deleted == {"ok": True, "deleted_job_id": job["job_id"]}
    with pytest.raises(ValueError, match="nicht gefunden"):
        manager.jobs.get(job["job_id"])


def test_workbench_job_actions_are_profile_scoped(tmp_path):
    manager = WorkbenchManager(tmp_path)
    job = manager.jobs.create_job(
        "Privater Auftrag",
        source="workbench",
        metadata={"profile": "PRIVAT"},
    )

    with pytest.raises(PermissionError, match="anderen Profil"):
        manager.cancel_job(job["job_id"], "BIZ")
    with pytest.raises(ValueError, match="zuerst abgebrochen"):
        manager.jobs.delete(job["job_id"])


def test_opencode_runner_uses_running_service_model_and_files(
    monkeypatch, tmp_path
):
    captured = {}
    thesis = tmp_path / "Thesis.pdf"
    thesis.write_bytes(b"%PDF-test")

    def fake_execute(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, stdout="Fertig", stderr="")

    manager = WorkbenchManager(tmp_path)
    monkeypatch.setattr(manager, "_execute_process", fake_execute)
    monkeypatch.setattr(manager, "_preflight_opencode", lambda **_kwargs: None)

    result = manager._run_opencode(
        executable="/bin/opencode",
        project_path=tmp_path,
        prompt="Begutachten",
        attachments=[thesis],
        model="ws_home/model",
        agent="thesis-reviewer",
        server_url="http://127.0.0.1:4096",
        timeout=120,
    )

    assert result == "Fertig"
    command = captured["command"]
    assert command[:2] == ["/bin/opencode", "run"]
    assert command[command.index("--attach") + 1] == "http://127.0.0.1:4096"
    assert command[command.index("--dir") + 1] == str(tmp_path)
    assert command[command.index("--file") + 1] == str(thesis)
    assert command[command.index("--model") + 1] == "ws_home/model"


def test_workbench_passes_real_opencode_agent_instead_of_domain_skill(
    monkeypatch, tmp_path
):
    captured = {}
    manager = WorkbenchManager(tmp_path)

    def fake_run_opencode(**kwargs):
        captured.update(kwargs)
        return "Fertig"

    monkeypatch.setattr(manager, "_run_opencode", fake_run_opencode)

    result = manager._run_harness(
        job_id="job_test",
        harness="opencode",
        executable="/bin/opencode",
        project_path=tmp_path,
        prompt="Arbeite nach dem Skill.",
        attachments=[],
        model="ws_home/model",
        skill="html-praesentationswerkstatt",
        harness_config={"agent": "build", "server_url": ""},
        timeout=120,
    )

    assert result == "Fertig"
    assert captured["agent"] == "build"


def test_codex_runner_uses_saved_chatgpt_login_model_and_stdin(
    monkeypatch, tmp_path
):
    captured = {}
    attachment_dir = tmp_path.parent / "private-upload"
    attachment_dir.mkdir()
    attachment = attachment_dir / "thesis.pdf"
    attachment.write_bytes(b"%PDF")

    def fake_execute(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, stdout="Plan erstellt", stderr="")

    manager = WorkbenchManager(tmp_path)
    monkeypatch.setattr(manager, "_execute_process", fake_execute)

    result = manager._run_codex(
        executable="/bin/codex",
        project_path=tmp_path,
        prompt="Erstelle einen Präsentationsplan.",
        attachments=[attachment],
        model="gpt-5.6-terra",
        sandbox="workspace-write",
        ephemeral=True,
        timeout=900,
    )

    assert result == "Plan erstellt"
    command = captured["command"]
    assert command[:2] == ["/bin/codex", "exec"]
    assert command[command.index("--model") + 1] == "gpt-5.6-terra"
    assert command[command.index("--add-dir") + 1] == str(attachment_dir)
    assert "--ephemeral" in command
    assert captured["kwargs"]["input_text"] == "Erstelle einen Präsentationsplan."


def test_codex_runner_attaches_visuals_to_multimodal_model(monkeypatch, tmp_path):
    captured = {}
    image = tmp_path / "visual.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nvisual")

    def fake_execute(command, **kwargs):
        captured["command"] = command
        return subprocess.CompletedProcess(command, 0, stdout="gesehen", stderr="")

    manager = WorkbenchManager(tmp_path)
    monkeypatch.setattr(manager, "_execute_process", fake_execute)

    manager._run_codex(
        executable="/bin/codex",
        project_path=tmp_path,
        prompt="Analysiere das Bild.",
        attachments=[image],
        model="gpt-5.6-sol",
        sandbox="workspace-write",
        ephemeral=True,
        timeout=120,
    )

    command = captured["command"]
    assert command[command.index("--image") + 1] == str(image.resolve())


def test_codex_model_selection_is_limited_to_visible_models():
    assert (
        WorkbenchManager._selected_model(
            {"model": "gpt-5.6-luna"}, "codex", {}
        )
        == "gpt-5.6-luna"
    )
    with pytest.raises(ValueError, match="freigegebenen Codex"):
        WorkbenchManager._selected_model(
            {"model": "invented-model"}, "codex", {}
        )


def _wait_for_status(manager, job_id, statuses, timeout=3):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = manager.public_job(job_id)
        if job["status"] in set(statuses):
            return job
        time.sleep(0.01)
    raise AssertionError(f"Job {job_id} erreichte {statuses} nicht.")


def _write_research_artifacts(output_path):
    sources = output_path / "sources"
    sources.mkdir(parents=True, exist_ok=True)
    (sources / "sources.json").write_text(
        '[{"id":"P1","title":"Geprüfte Quelle","url":"https://example.org"}]\n',
        encoding="utf-8",
    )
    (sources / "source-overview.md").write_text(
        "# Quellen\n\n- P1\n", encoding="utf-8"
    )


def test_presentation_scaffold_copies_complete_local_template(tmp_path):
    project = tmp_path / "BrainVault"
    project.mkdir()
    template = tmp_path / "resources" / "html_presentation_workshop" / "template"
    (template / "assets").mkdir(parents=True)
    (template / "briefing.html").write_text("<html>Briefing</html>", encoding="utf-8")
    (template / "assets" / "briefing.css").write_text("body{}", encoding="utf-8")
    config = default_config("Linux")
    config["opencode"]["projects"] = {"BrainVault": str(project)}
    manager = WorkbenchManager(tmp_path)

    result = manager.submit(
        {
            "tile_id": "html-presentation-scaffold",
            "project": "BrainVault",
            "output_path": "Vorträge/Neues Grundgerüst",
        },
        config,
        "PRIVAT",
    )
    job = _wait_for_status(manager, result["job"]["job_id"], {"SUCCEEDED", "FAILED"})

    assert job["status"] == "SUCCEEDED"
    output = project / "Vorträge" / "Neues Grundgerüst"
    assert (output / "briefing.html").is_file()
    assert (output / "assets" / "briefing.css").is_file()
    assert (output / "README.md").is_file()


def test_presentation_plan_waits_for_edited_approval_then_builds(
    monkeypatch, tmp_path
):
    project = tmp_path / "BrainVault"
    project.mkdir()
    manager = WorkbenchManager(tmp_path)
    config = default_config("Linux")
    config["opencode"].update(
        {
            "enabled": True,
            "projects": {"BrainVault": str(project)},
            "default_project": "BrainVault",
        }
    )
    monkeypatch.setattr(workbench, "find_opencode_executable", lambda: "/bin/opencode")
    calls = []

    def fake_run_opencode(**kwargs):
        calls.append(kwargs)
        output_path = Path(kwargs["extra_env"]["TRINITY_PRESENTATION_OUTPUT"])
        if len(calls) == 1:
            _write_research_artifacts(output_path)
            (output_path / "presentation-plan.md").write_text(
                "# Plan\n\n- slide-01: Einstieg\n", encoding="utf-8"
            )
            return "Plan erstellt"
        (output_path / "presentation.html").write_text(
            "<html>Präsentation</html>", encoding="utf-8"
        )
        (output_path / "review.html").write_text(
            "<html>Review</html>", encoding="utf-8"
        )
        return "Präsentation und Review geprüft"

    monkeypatch.setattr(manager, "_run_opencode", fake_run_opencode)
    result = manager.submit(
        {
            "tile_id": "html-presentation-workshop",
            "harness": "opencode",
            "project": "BrainVault",
            "output_path": "Vorträge/Agentic AI",
            "title": "Agentic AI",
            "audience": "Studierende",
            "duration_minutes": 45,
            "outline": "Einstieg, Architektur, Übung, Synthese",
            "languages": ["de"],
            "image_provider": "kie",
            "image_model": "gpt-image-2-text-to-image",
            "attachments": [],
        },
        config,
        "PRIVAT",
    )
    job_id = result["job"]["job_id"]
    waiting = _wait_for_status(
        manager, job_id, {"WAITING_FOR_APPROVAL", "FAILED"}
    )

    assert waiting["status"] == "WAITING_FOR_APPROVAL"
    plan_event = next(
        event for event in reversed(waiting["events"]) if event["details"].get("plan")
    )
    assert "slide-01" in plan_event["details"]["plan"]
    assert not (project / "Vorträge" / "Agentic AI" / "presentation.html").exists()

    approved = manager.approve_presentation(
        {
            "job_id": job_id,
            "plan": "# Überarbeiteter Plan\n\n- slide-01: Neuer Einstieg\n",
        },
        config,
        "PRIVAT",
    )
    assert approved["job"]["status"] == "RUNNING"
    finished = _wait_for_status(manager, job_id, {"SUCCEEDED", "FAILED"})

    assert finished["status"] == "SUCCEEDED"
    output = project / "Vorträge" / "Agentic AI"
    assert "Neuer Einstieg" in (output / "presentation-plan.md").read_text()
    assert (output / "presentation.html").is_file()
    assert (output / "review.html").is_file()
    assert calls[0]["agent"] == "build"
    assert calls[0]["timeout"] >= 900
    assert calls[1]["prompt"].startswith("FREIGABE")


def test_presentation_plan_accepts_empty_content_and_creates_own_structure(
    monkeypatch, tmp_path
):
    project = tmp_path / "BrainVault"
    project.mkdir()
    manager = WorkbenchManager(tmp_path)
    config = default_config("Linux")
    config["opencode"].update(
        {
            "enabled": True,
            "projects": {"BrainVault": str(project)},
            "default_project": "BrainVault",
            "timeout_seconds": 180,
        }
    )
    monkeypatch.setattr(workbench, "find_opencode_executable", lambda: "/bin/opencode")

    def fake_run_opencode(**kwargs):
        output_path = Path(kwargs["extra_env"]["TRINITY_PRESENTATION_OUTPUT"])
        _write_research_artifacts(output_path)
        (output_path / "presentation-plan.md").write_text(
            "# Eigene Grobstruktur\n", encoding="utf-8"
        )
        assert "entwickle selbst eine sinnvolle Grobstruktur" in kwargs["prompt"]
        assert kwargs["timeout"] == 900
        return "Eigene Grobstruktur erstellt"

    monkeypatch.setattr(manager, "_run_opencode", fake_run_opencode)
    result = manager.submit(
        {
            "tile_id": "html-presentation-workshop",
            "harness": "opencode",
            "project": "BrainVault",
            "attachments": [],
        },
        config,
        "PRIVAT",
    )

    waiting = _wait_for_status(
        manager,
        result["job"]["job_id"],
        {"WAITING_FOR_APPROVAL", "FAILED"},
    )
    assert waiting["status"] == "WAITING_FOR_APPROVAL"
    assert waiting["metadata"]["title"].startswith("Neuer Entwurf")
    assert Path(waiting["metadata"]["output_path"]).parts[0] == "HTML-Präsentationen"


def test_presentation_modernization_requires_one_deck_and_creates_analysis_contract(
    monkeypatch, tmp_path
):
    project = tmp_path / "BrainVault"
    project.mkdir()
    manager = WorkbenchManager(tmp_path)
    config = default_config("Linux")
    config["opencode"].update(
        {
            "enabled": True,
            "projects": {"BrainVault": str(project)},
            "default_project": "BrainVault",
        }
    )
    monkeypatch.setattr(workbench, "find_opencode_executable", lambda: "/bin/opencode")

    with pytest.raises(ValueError, match="genau eine"):
        manager.submit(
            {
                "tile_id": "html-presentation-modernize",
                "harness": "opencode",
                "project": "BrainVault",
                "attachments": [],
            },
            config,
            "PRIVAT",
        )

    captured = {}

    def fake_run_opencode(**kwargs):
        captured.update(kwargs)
        output_path = Path(kwargs["extra_env"]["TRINITY_PRESENTATION_OUTPUT"])
        _write_research_artifacts(output_path)
        (output_path / "source-deck-analysis.md").write_text(
            "# Ausgangspräsentation\n", encoding="utf-8"
        )
        (output_path / "source-media-inventory.json").write_text(
            "{}\n", encoding="utf-8"
        )
        (output_path / "presentation-plan.md").write_text(
            "# Modernisierungsplan\n", encoding="utf-8"
        )
        return "Modernisierungsplan erstellt"

    monkeypatch.setattr(manager, "_run_opencode", fake_run_opencode)
    result = manager.submit(
        {
            "tile_id": "html-presentation-modernize",
            "presentation_mode": "modernize",
            "harness": "opencode",
            "project": "BrainVault",
            "attachments": [
                {
                    "role": "source-deck",
                    "name": "Alte Vorlesung.pptx",
                    "data_base64": base64.b64encode(b"pptx-test").decode(),
                }
            ],
        },
        config,
        "PRIVAT",
    )
    waiting = _wait_for_status(
        manager, result["job"]["job_id"], {"WAITING_FOR_APPROVAL", "FAILED"}
    )

    assert waiting["status"] == "WAITING_FOR_APPROVAL"
    assert waiting["metadata"]["presentation_mode"] == "modernize"
    assert waiting["metadata"]["title"] == "Alte Vorlesung"
    assert "source-deck-analysis.md" in captured["prompt"]
    output = project / waiting["metadata"]["output_path"]
    request = (output / "presentation-request.json").read_text(encoding="utf-8")
    assert '"presentation_mode": "modernize"' in request
    assert (output / "reference-material" / "Alte Vorlesung.pptx").is_file()


def test_presentation_paths_cannot_escape_configured_project(tmp_path):
    project = tmp_path / "BrainVault"
    project.mkdir()

    with pytest.raises(ValueError, match="innerhalb"):
        WorkbenchManager._project_member(
            project,
            "../außerhalb",
            label="Ausgabeordner",
            require_exists=False,
            allow_project_root=False,
        )


def test_workbench_provider_secrets_are_persistent_but_never_returned(tmp_path):
    manager = WorkbenchManager(tmp_path)
    config = default_config("Linux")

    result = manager.save_secrets(
        {"kie_ai": "kie-secret", "fal_ai": "fal-secret"}, config
    )

    assert result == {
        "ok": True,
        "kie_configured": True,
    }
    assert "secret" not in str(result)
    assert manager.secret_status(config)["kie_configured"] is True
    stored = manager._load_secrets(config)
    assert stored["kie_ai"] == "kie-secret"
    assert "fal_ai" not in stored
    if os.name != "nt":
        assert manager.secrets_path.stat().st_mode & 0o077 == 0


def test_opencode_timeout_error_never_exposes_full_command(monkeypatch, tmp_path):
    def fake_execute(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    manager = WorkbenchManager(tmp_path)
    monkeypatch.setattr(manager, "_execute_process", fake_execute)
    monkeypatch.setattr(manager, "_preflight_opencode", lambda **_kwargs: None)

    with pytest.raises(TimeoutError, match="Zeitlimit von 15 Minuten") as error:
        manager._run_opencode(
            executable="/bin/opencode",
            project_path=tmp_path,
            prompt="privater sehr langer Prompt",
            attachments=[],
            model="model",
            agent="agent",
            server_url="",
            timeout=900,
        )
    assert "privater sehr langer Prompt" not in str(error.value)

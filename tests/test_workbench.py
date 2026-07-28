import base64
import subprocess
import time
from pathlib import Path

import pytest

import workbench
from configuration import default_config
from workbench import WorkbenchManager


def test_catalog_exposes_thesis_tile_profile_and_only_opencode(monkeypatch, tmp_path):
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
    monkeypatch.setattr(workbench, "find_opencode_executable", lambda: "/bin/opencode")
    monkeypatch.setattr(manager, "_opencode_models", lambda _config: [])

    catalog = manager.catalog(config, "BIZ")

    assert catalog["profile"] == "BIZ"
    assert catalog["harnesses"][0]["id"] == "opencode"
    assert catalog["harnesses"][0]["available"] is True
    assert catalog["projects"][0]["name"] == "Lehre"
    assert catalog["categories"][0]["tiles"][0]["id"] == "thesis-reviewer"
    assert catalog["categories"][0]["tiles"][0]["available"] is True
    presentation_tiles = catalog["categories"][1]["tiles"]
    assert [tile["id"] for tile in presentation_tiles] == [
        "html-presentation-workshop",
        "html-presentation-scaffold",
    ]
    assert presentation_tiles[0]["available"] is True
    assert catalog["presentation"]["default_image_provider"] == "kie"


@pytest.mark.parametrize("profile", ["BIZ", "PRIVAT", "TEST"])
def test_thesis_tile_is_available_in_every_profile(tmp_path, profile):
    manager = WorkbenchManager(tmp_path)
    catalog = manager.catalog(default_config("Linux"), profile)

    tile = catalog["categories"][0]["tiles"][0]
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


def test_opencode_runner_uses_running_service_model_and_files(
    monkeypatch, tmp_path
):
    captured = {}
    thesis = tmp_path / "Thesis.pdf"
    thesis.write_bytes(b"%PDF-test")

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, stdout="Fertig", stderr="")

    monkeypatch.setattr(workbench.subprocess, "run", fake_run)

    result = WorkbenchManager._run_opencode(
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
    assert command[command.index("--agent") + 1] == "thesis-reviewer"


def _wait_for_status(manager, job_id, statuses, timeout=3):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = manager.public_job(job_id)
        if job["status"] in set(statuses):
            return job
        time.sleep(0.01)
    raise AssertionError(f"Job {job_id} erreichte {statuses} nicht.")


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
            "image_model": "nano-banana-2",
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
    assert calls[0]["agent"] == "html-praesentationswerkstatt"
    assert calls[1]["prompt"].startswith("FREIGABE")


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
        "fal_configured": True,
    }
    assert "secret" not in str(result)
    assert manager.secret_status(config)["kie_configured"] is True
    if hasattr(manager.secrets_path.stat(), "st_mode"):
        assert manager.secrets_path.stat().st_mode & 0o077 == 0

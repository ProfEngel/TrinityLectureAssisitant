import base64
import subprocess

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

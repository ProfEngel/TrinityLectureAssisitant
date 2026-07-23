from configuration import load_config, save_config
from doctor import _ssl_status, doctor_exit_code, run_doctor


def test_ssl_check_reports_missing_runtime():
    def fail_import(_name):
        raise ImportError("DLL fehlt")

    available, message = _ssl_status(fail_import)

    assert available is False
    assert "DLL fehlt" in message


def test_doctor_accepts_headless_installation(tmp_path):
    core = tmp_path / "core"
    core.mkdir()
    (tmp_path / "trinity_launcher.py").touch()
    config = load_config(core / "config.json", platform_name="Linux")
    config["system"].update(
        {
            "eyes_ui_enabled": False,
            "classic_ui_enabled": False,
            "terminal_cli_enabled": True,
            "show_terminal": True,
        }
    )
    config["llm"]["local"]["model"] = "local-model"
    config["canvas"]["enabled"] = False
    save_config(core / "config.json", config)

    results = run_doctor(tmp_path)

    assert doctor_exit_code(results) == 0
    assert any(
        item["name"] == "Oberflächen" and "terminal" in item["message"]
        for item in results
    )
    assert any(
        item["name"] == "Canvas" and "deaktiviert" in item["message"]
        for item in results
    )


def test_doctor_fix_creates_support_directories(tmp_path):
    core = tmp_path / "core"
    core.mkdir()
    (tmp_path / "trinity_launcher.py").touch()
    (core / "Soul.md.example").write_text("Soul", encoding="utf-8")
    (core / "User.md.example").write_text("User", encoding="utf-8")
    config = load_config(core / "config.json", platform_name="Linux")
    config["system"].update(
        {
            "eyes_ui_enabled": False,
            "classic_ui_enabled": False,
            "terminal_cli_enabled": True,
        }
    )
    save_config(core / "config.json", config)

    run_doctor(tmp_path, fix=True)

    assert (core / "Soul.md").is_file()
    assert (core / "User.md").is_file()
    assert (tmp_path / "memory").is_dir()
    assert (tmp_path / "logs").is_dir()


def test_doctor_reports_canvas_ui_failure_as_error(tmp_path, monkeypatch):
    core = tmp_path / "core"
    core.mkdir()
    config = load_config(core / "config.json", platform_name="Windows")
    config["system"]["terminal_cli_enabled"] = True
    save_config(core / "config.json", config)
    monkeypatch.setattr(
        "doctor.CanvasManager.status",
        lambda self: {
            "state": "ui_unavailable",
            "message": "Der Canvas-Dienst läuft, aber die Weboberfläche ist nicht erreichbar (HTTP 404).",
        },
    )

    results = run_doctor(tmp_path)

    canvas = next(item for item in results if item["name"] == "Canvas")
    assert canvas["level"] == "ERROR"
    assert "HTTP 404" in canvas["message"]
    assert doctor_exit_code(results) == 1

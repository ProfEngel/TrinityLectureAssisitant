from types import SimpleNamespace

from canvas_manager import CanvasManager
from configuration import save_config


def _manager(tmp_path):
    home = tmp_path / "Trinity"
    install = tmp_path / "Canvas"
    runtime = tmp_path / "Runtime"
    (home / "core").mkdir(parents=True)
    (install / "dist-server" / "server").mkdir(parents=True)
    (install / "dist").mkdir()
    (install / "package.json").write_text("{}", encoding="utf-8")
    (install / "dist-server" / "server" / "index.js").write_text("", encoding="utf-8")
    (install / "dist" / "index.html").write_text("", encoding="utf-8")
    save_config(
        home / "core" / "config.json",
        {
            "control_plane": {"runtime_root": str(runtime)},
            "canvas": {"enabled": True, "install_dir": str(install), "port": 8787},
        },
    )
    return CanvasManager(home), install, runtime


def test_canvas_status_hides_internal_service_details_from_installation(tmp_path, monkeypatch):
    manager, install, runtime = _manager(tmp_path)
    monkeypatch.setattr(manager, "is_running", lambda timeout=0.6: False)

    status = manager.status()

    assert status["installed"] is True
    assert status["built"] is True
    assert status["install_dir"] == str(install)
    assert status["data_dir"] == str(runtime / "canvas")
    assert status["url"] == "http://127.0.0.1:8787"


def test_canvas_start_uses_one_local_production_service(tmp_path, monkeypatch):
    manager, install, runtime = _manager(tmp_path)
    running = iter([False, True])
    monkeypatch.setattr(manager, "is_running", lambda timeout=0.6: next(running))
    monkeypatch.setattr("canvas_manager.shutil.which", lambda name: "/usr/bin/node" if name == "node" else None)
    captured = {}

    class Process:
        pid = 4242

        def poll(self):
            return None

    def fake_popen(command, **kwargs):
        captured.update({"command": command, **kwargs})
        return Process()

    monkeypatch.setattr("canvas_manager.subprocess.Popen", fake_popen)

    process = manager.start(log_handle=SimpleNamespace())

    assert process.pid == 4242
    assert captured["command"] == [
        "/usr/bin/node",
        str(install / "dist-server" / "server" / "index.js"),
    ]
    assert captured["env"]["NODE_ENV"] == "production"
    assert captured["env"]["HOST"] == "127.0.0.1"
    assert captured["env"]["PORT"] == "8787"
    assert captured["env"]["DATA_DIR"] == str(runtime / "canvas")
    assert (runtime / "canvas" / "canvas.pid").read_text(encoding="utf-8") == "4242"


def test_canvas_can_bind_to_one_explicit_tailnet_address(tmp_path):
    manager, _, _ = _manager(tmp_path)
    manager.settings["host"] = "100.64.0.42"

    configured = CanvasManager(manager.home, manager.config)

    assert configured.host == "100.64.0.42"
    assert configured.url == "http://100.64.0.42:8787"

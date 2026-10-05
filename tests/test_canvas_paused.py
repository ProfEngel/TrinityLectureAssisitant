"""The retained legacy component must not participate in normal Desktop use."""
import ast
from pathlib import Path

from canvas_manager import CanvasManager
from configuration import default_config


ROOT = Path(__file__).resolve().parents[1]


def test_canvas_defaults_off_and_leaves_existing_data_untouched(tmp_path, monkeypatch):
    assert default_config()["canvas"]["enabled"] is False
    manager = CanvasManager(tmp_path, {})
    manager.data_dir.mkdir(parents=True)
    data = manager.data_dir / "retained.txt"
    data.write_text("keep")
    monkeypatch.setattr(manager, "is_running", lambda: (_ for _ in ()).throw(AssertionError("no network probe")))
    assert not manager.enabled
    assert manager.start() is None
    assert data.read_text() == "keep"


def test_launcher_has_no_canvas_start_and_ui_has_no_canvas_tab():
    tree = ast.parse((ROOT / "trinity_launcher.py").read_text(encoding="utf-8"))
    assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                   and isinstance(n.func.value, ast.Name) and n.func.value.id == "canvas_manager"
                   and n.func.attr == "start" for n in ast.walk(tree))
    ui = (ROOT / "trinity_classic.py").read_text(encoding="utf-8")
    assert 'addTab(canvas_tab' not in ui
    assert 'self.canvas_workspace' not in ui


def test_installers_and_ci_do_not_fetch_or_build_canvas():
    for name in ("install_mac.sh", "install_windows.ps1", ".github/workflows/cross-platform-smoke.yml"):
        source = (ROOT / name).read_text(encoding="utf-8")
        assert "--recurse-submodules" not in source
        assert "npm ci" not in source
        assert "$canvasZipUrl" not in source
        assert "Build and smoke-test Trinity Canvas" not in source

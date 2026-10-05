import os
import pytest
pytestmark = pytest.mark.usefixtures("qt_app")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from core.debug_console import DebugConsole


def test_terminal_tails_and_hides_without_quitting(tmp_path):
    app = QApplication.instance() or QApplication([])
    path = tmp_path / "logs/client.log"
    path.parent.mkdir()
    path.write_text("Du: Test\n")
    console = DebugConsole(tmp_path)
    console.set_enabled(True)
    assert "Du: Test" in console.text.toPlainText()
    with path.open("a") as handle:
        handle.write("Server · LLM: fertig\n")
    console.refresh()
    assert "LLM: fertig" in console.text.toPlainText()
    assert console.text.toPlainText().count("Du: Test") == 1
    console.close()
    assert not console.isVisible()
    assert not console.timer.isActive()

import sys
from pathlib import Path
import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]
CORE_DIR = ROOT_DIR / "core"

for path in (ROOT_DIR, CORE_DIR):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)


@pytest.fixture(scope="session")
def qt_app():
    """Keep Qt alive until all test-owned widgets/timers have been disposed.

    A local QApplication variable can be collected between tests, while
    widget reference cycles are only collected much later. On Windows that
    lets QWidget destructors run after their application has gone away.
    """
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    return app

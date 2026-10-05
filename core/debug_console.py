"""Read-only terminal-style live log window; hiding it never stops Trinity."""
from pathlib import Path
from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QDialog, QPlainTextEdit, QVBoxLayout


class DebugConsole(QDialog):
    closed = Signal()

    def __init__(self, home):
        super().__init__()
        self.path = Path(home) / "logs/client.log"
        self.offset = 0
        self.setWindowTitle("Trinity · Debug-Terminal")
        self.resize(1050, 600)
        self.text = QPlainTextEdit(self)
        self.text.setReadOnly(True)
        self.text.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.text.setMaximumBlockCount(2500)
        layout = QVBoxLayout(self)
        layout.addWidget(self.text)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)

    def set_enabled(self, enabled):
        if enabled:
            self.refresh()
            self.timer.start(500)
            self.show()
            self.raise_()
        else:
            self.timer.stop()
            self.hide()

    def refresh(self):
        try:
            with self.path.open("rb") as handle:
                size = self.path.stat().st_size
                if not self.offset or size < self.offset:
                    self.offset = max(0, size - 24000)
                handle.seek(self.offset)
                data = handle.read(64000)
                self.offset = handle.tell()
            if data:
                self.text.appendPlainText(data.decode("utf-8", errors="replace").rstrip())
        except OSError:
            pass

    def closeEvent(self, event):
        self.set_enabled(False)
        self.closed.emit()
        event.accept()

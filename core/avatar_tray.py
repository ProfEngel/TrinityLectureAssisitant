"""Small, gently blinking Trinity eyes for the desktop menu bar."""

import random
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QRectF, QSettings, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon
from desktop_audio_activity import desktop_audio_active


def eyes_icon(state="idle", closed=False, audio_active=False, light=True,
              audio_color=True, show_dot=False):
    # Use a taller face aspect ratio: macOS fits the entire icon into its status
    # item, so a wide, shallow canvas makes the face look unexpectedly tiny.
    # Render at 2x for Retina; reserve space outside the visor for audio activity.
    pixmap = QPixmap(120 if show_dot else 96, 76)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    face_color = ("#ff9f28" if audio_active else "#e8eeee") if audio_color else (
        "#e8eeee" if light else "#0a0a0a")
    painter.setBrush(QColor(face_color))
    painter.drawRoundedRect(QRectF(1, 1, 45, 36), 15, 15)
    height = 2 if closed else (9 if state == "listening" else 6)
    painter.setBrush(QColor("#23b477"))
    for x in (10, 28):
        painter.drawRoundedRect(QRectF(x, 19 - height / 2, 9, height), 2.25, 2.25)
    if audio_active and show_dot:
        painter.setBrush(QColor("#f0a044"))
        painter.drawEllipse(QRectF(51, 15, 8, 8))
    painter.end()
    return QIcon(pixmap)


class AvatarTray(QObject):
    def __init__(self, window, speaker_control, settings=None, home=None):
        super().__init__(window)
        self.window = window
        self.settings = settings if settings is not None else QSettings("Trinity", "DesktopAvatar")
        self.compact = False
        self.state = "idle"
        self.notification = False
        self.closed = False
        self.home = Path(home) if home is not None else Path(__file__).resolve().parents[1]
        self.audio_active = desktop_audio_active(self.home)
        self.light = self.settings.value("lightAppearance", True, type=bool)
        self.audio_color = self.settings.value("audioColor", True, type=bool)
        self.show_dot = self.settings.value("showAudioDot", False, type=bool)
        self.icon = QSystemTrayIcon(eyes_icon(audio_active=self.audio_active, light=self.light), self)
        self.icon.setToolTip("Trinity")
        self.menu = QMenu(window)
        self.menu.addAction("Avatar anzeigen", self.restore)
        self.menu.addAction("Chat öffnen", window.open_chat)
        self.result_action = self.menu.addAction("Ergebnis / Hinweis anzeigen", window.show_latest_content)
        self.light_action = self.menu.addAction("Weiße MiniTrinity")
        self.light_action.setCheckable(True)
        self.light_action.setChecked(self.light)
        self.light_action.toggled.connect(self.set_light)
        self.audio_color_action = self.menu.addAction("Audio durch Farbe anzeigen (Orange/Weiß)")
        self.audio_color_action.setCheckable(True)
        self.audio_color_action.setChecked(self.audio_color)
        self.audio_color_action.toggled.connect(self.set_audio_color)
        self.dot_action = self.menu.addAction("Audiopunkt anzeigen")
        self.dot_action.setCheckable(True)
        self.dot_action.setChecked(self.show_dot)
        self.dot_action.toggled.connect(self.set_show_dot)
        self.light_action.setEnabled(not self.audio_color)
        self.menu.addSeparator()
        self.menu.addAction("Hier auf diesem Computer antworten", speaker_control.claim)
        self.menu.addAction("Sprachausgabe stumm", speaker_control.mute)
        self.menu.addSeparator()
        self.menu.addAction("Einstellungen …", window.open_settings)
        self.menu.addAction("Trinity beenden", QApplication.instance().quit)
        if sys.platform == "darwin":
            # Avoid native NSMenu tracking: Qt's Cocoa bridge can ask a
            # SysDefined NSEvent for clickCount and abort the whole UI.
            self.icon.activated.connect(self._show_menu)
        else:
            self.icon.setContextMenu(self.menu)
        self.blink_timer = QTimer(self)
        self.blink_timer.setSingleShot(True)
        self.blink_timer.timeout.connect(self._blink)
        self.open_timer = QTimer(self)
        self.open_timer.setSingleShot(True)
        self.open_timer.setInterval(140)
        self.open_timer.timeout.connect(self._open_eyes)
        self.audio_timer = QTimer(self)
        self.audio_timer.setInterval(500)
        self.audio_timer.timeout.connect(self.refresh_audio_activity)
        self.audio_timer.start()
        self._redraw()

    def apply_startup_mode(self):
        if self.settings.value("menuBarOnly", False, type=bool):
            if self.minimize():
                return
        self.window.show()

    def _show_menu(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.Context):
            # Leave the native status-item callback before opening a Qt popup.
            position = QCursor.pos()
            QTimer.singleShot(0, lambda: self.menu.popup(position))

    def minimize(self):
        # Never hide the only way back on desktops without a system tray.
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return False
        self.compact = True
        self.icon.show()
        self.window.hide()
        self.window.chat_window.hide()
        self.window.content_window.hide()
        self.settings.setValue("menuBarOnly", True)
        self.blink_timer.start(random.randint(5000, 9000))
        return True

    def restore(self):
        self.compact = False
        self.blink_timer.stop()
        self.open_timer.stop()
        self.closed = False
        self.icon.hide()
        self.settings.setValue("menuBarOnly", False)
        self.window.show()
        self.window.raise_()

    def set_state(self, state):
        self.state = state
        self._redraw()

    def set_notification(self, enabled):
        self.notification = enabled
        self.result_action.setText("Ergebnis / Hinweis anzeigen" + (" · Neu" if enabled else ""))

    def set_light(self, enabled):
        self.light = enabled
        self.settings.setValue("lightAppearance", enabled)
        self._redraw()

    def refresh_audio_activity(self):
        active = desktop_audio_active(self.home)
        if active != self.audio_active:
            self.audio_active = active
            self._redraw()

    def set_audio_color(self, enabled):
        self.audio_color = enabled
        self.settings.setValue("audioColor", enabled)
        self.light_action.setEnabled(not enabled)
        self._redraw()

    def set_show_dot(self, enabled):
        self.show_dot = enabled
        self.settings.setValue("showAudioDot", enabled)
        self._redraw()

    def _redraw(self):
        self.icon.setIcon(eyes_icon(self.state, self.closed, self.audio_active, self.light,
                                   self.audio_color, self.show_dot))
        self.icon.setToolTip("Trinity · Mikrofon oder Sprachausgabe aktiv" if self.audio_active
                             else "Trinity · Mikrofon und Sprachausgabe inaktiv")

    def _blink(self):
        if not self.compact:
            return
        self.closed = True
        self._redraw()
        self.open_timer.start()

    def _open_eyes(self):
        self.closed = False
        self._redraw()
        if self.compact:
            self.blink_timer.start(random.randint(5000, 9000))

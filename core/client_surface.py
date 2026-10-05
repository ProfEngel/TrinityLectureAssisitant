"""Compact macOS controls for the remote Trinity desktop client."""

from __future__ import annotations

import random
import threading

from PySide6.QtCore import QObject, QPoint, QRectF, QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QPainter, QPen
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidget

from .avatar_tray import eyes_icon


class FloatingFace(QWidget):
    """Optional draggable face; a double click returns to menu-bar-only mode."""

    def __init__(self, tray):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.tray = tray
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow, True)
        self.setFixedSize(136, 110)
        self._drag_offset = None
        self._eyes_closed = False
        self._blink_timer = QTimer(self)
        self._blink_timer.setSingleShot(True)
        self._blink_timer.timeout.connect(self._blink)
        self._open_timer = QTimer(self)
        self._open_timer.setSingleShot(True)
        self._open_timer.timeout.connect(self._open_eyes)

    def show_face(self):
        screen = QApplication.primaryScreen()
        if screen and not self.isVisible():
            area = screen.availableGeometry()
            self.move(area.right() - self.width() - 24, area.bottom() - self.height() - 24)
        self.show()
        self.raise_()
        self._blink_timer.start(random.randint(4500, 8500))

    def hide_face(self):
        self._blink_timer.stop()
        self._open_timer.stop()
        self.hide()

    def _blink(self):
        self._eyes_closed = True
        self.update()
        self._open_timer.start(145)

    def _open_eyes(self):
        self._eyes_closed = False
        self.update()
        if self.isVisible():
            self._blink_timer.start(random.randint(4500, 8500))

    def paintEvent(self, _event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#ff9f28" if self.tray.audio_active else "#0a0a0a"))
        painter.drawRoundedRect(QRectF(16, 25, 104, 62), 29, 29)
        if self.tray.dictating:
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor("#ff3b30"), 3))
            painter.drawRoundedRect(QRectF(16, 25, 104, 62), 29, 29)
            painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#23b477"))
        eye_height = 3 if self._eyes_closed else 12
        for x in (41, 79):
            painter.drawRoundedRect(QRectF(x, 56 - eye_height / 2, 16, eye_height), 5, 5)

    def mouseDoubleClickEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.tray.set_floating(False)
            event.accept()

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        elif event.button() == Qt.RightButton:
            self.tray.show_menu(event.globalPosition().toPoint())
            event.accept()

    def mouseMoveEvent(self, event):  # noqa: N802
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event):  # noqa: N802
        self._drag_offset = None
        event.accept()


class _StatusBus(QObject):
    updated = Signal(object, object, object)


class ClientTray(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.settings = QSettings("Trinity", "RemoteClientSurface")
        self.audio_active = False
        self.dictating = False
        self._status_bus = _StatusBus(self)
        self._status_bus.updated.connect(self._apply_status)
        self._poll_stop = threading.Event()
        self.icon = QSystemTrayIcon(eyes_icon(), self)
        self.menu = QMenu(window)
        self.menu.addAction("Trinity öffnen", window.open_companion)
        self.floating_action = self.menu.addAction("Schwebende Trinity anzeigen")
        self.floating_action.setCheckable(True)
        self.floating_action.triggered.connect(self.set_floating)
        self.menu.addSeparator()
        self.input_action = self.menu.addAction("Hier auf dem Mac zuhören")
        self.input_action.setCheckable(True)
        self.input_action.triggered.connect(self.set_microphone)
        self.output_action = self.menu.addAction("Hier auf dem Mac antworten", window.claim_speaker)
        self.output_action.setCheckable(True)
        self.menu.addAction("Sprachausgabe stumm", window.mute_speaker)
        self.dictation_action = self.menu.addAction("Diktat starten")
        self.dictation_action.setCheckable(True)
        self.dictation_action.triggered.connect(lambda checked: window.set_dictation_from_menu(checked))
        self.vision_action = self.menu.addAction("Aktives Fenster erfassen")
        self.vision_action.setCheckable(True)
        self.vision_action.toggled.connect(window.set_window_sharing)
        self.vision_action.setChecked(self.settings.value("windowOnDemand", True, type=bool))
        self.menu.addAction("Letzte Antwort an Cursorposition einsetzen …", window.insert_last_answer)
        self.menu.addSeparator()
        self.mode_menu = self.menu.addMenu("Gesprächsmodus")
        self.lecture_action = self.mode_menu.addAction("Vorlesung · Wakeword Trinity")
        self.lecture_action.setCheckable(True)
        self.lecture_action.triggered.connect(lambda: window.set_runtime_mode("lecture"))
        self.office_action = self.mode_menu.addAction("Büro · Konversation")
        self.office_action.setCheckable(True)
        self.office_action.triggered.connect(lambda: window.set_runtime_mode("office"))
        self.menu.addSeparator()
        self.system_audio_action = self.menu.addAction("Alle Mac-Töne mithören (BlackHole 16ch)")
        self.system_audio_action.setCheckable(True)
        self.system_audio_action.setChecked(self.settings.value("hearMacAudio", False, type=bool))
        self.system_audio_action.toggled.connect(self.set_system_audio)
        self.broadcast_action = self.menu.addAction("Trinity in Teams/OBS sprechen lassen (BlackHole 2ch)")
        self.broadcast_action.setCheckable(True)
        self.broadcast_action.setChecked(self.settings.value("broadcastTrinity", False, type=bool))
        self.broadcast_action.toggled.connect(self.set_broadcast)
        self.menu.addSeparator()
        for title in ("Vortrag", "TrinityHUB", "Medienwerkstatt"):
            self.menu.addAction(title, lambda _checked=False, name=title: window.open_view(name))
        self.debug_action = self.menu.addAction("Debug-Terminal")
        self.debug_action.setCheckable(True)
        self.debug_action.triggered.connect(lambda checked: window.set_debug_terminal(checked))
        self.menu.addAction("Einstellungen …", window.open_settings)
        self.menu.addSeparator()
        self.menu.addAction("Trinity beenden", QApplication.instance().quit)
        self.face = FloatingFace(self)
        self._foreground_timer = QTimer(self)
        self._foreground_timer.timeout.connect(window.remember_foreground_app)
        self._foreground_timer.start(500)
        self.icon.activated.connect(self._activated)
        if QApplication.platformName() != "cocoa":
            self.icon.setContextMenu(self.menu)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.icon.show()
        if self.settings.value("floatingVisible", False, type=bool):
            self.set_floating(True)
        self._poller = threading.Thread(target=self._poll_status, daemon=True, name="trinity-client-tray-status")
        self._poller.start()

    def _activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.Context):
            QTimer.singleShot(0, lambda: self.show_menu(QCursor.pos()))
        elif reason == QSystemTrayIcon.DoubleClick:
            self.window.open_companion()

    def show_menu(self, position: QPoint):
        self.window.remember_foreground_app()
        self.menu.popup(position)

    def set_dictating(self, active):
        self.dictating = bool(active)
        self.dictation_action.setChecked(self.dictating)
        self.dictation_action.setText("Diktat stoppen" if self.dictating else "Diktat starten")
        self.icon.setIcon(eyes_icon(audio_active=self.audio_active, dictating=self.dictating))
        self.face.update()

    def set_floating(self, visible: bool):
        visible = bool(visible)
        self.settings.setValue("floatingVisible", visible)
        self.floating_action.setChecked(visible)
        if visible:
            self.face.show_face()
        else:
            self.face.hide_face()

    @staticmethod
    def _audio_device_available(name: str, direction: str) -> bool:
        try:
            import sounddevice as sd
            channel_key = "max_input_channels" if direction == "input" else "max_output_channels"
            return any(name.casefold() in str(device["name"]).casefold() and device[channel_key] >= 2
                       for device in sd.query_devices())
        except Exception:
            return False

    def set_system_audio(self, enabled: bool):
        if enabled and not self._audio_device_available("BlackHole 16ch", "input"):
            self.system_audio_action.setChecked(False)
            self.window.statusBar().showMessage("BlackHole 16ch fehlt: einmal mit Administratorrechten installieren und Mac neu starten", 10000)
            return
        self.settings.setValue("hearMacAudio", enabled)
        self.settings.sync()
        if enabled:
            self.window.claim_microphone()
        self.window.statusBar().showMessage(
            "Mac-Mikrofon gewählt; alle Mac-Töne zusätzlich nur bei Multi-Output mit BlackHole 16ch (G2 hat weiterhin Vorrang)"
            if enabled else "Mithören aller Mac-Töne ausgeschaltet", 10000,
        )

    def set_broadcast(self, enabled: bool):
        if enabled and not self._audio_device_available("BlackHole 2ch", "output"):
            self.broadcast_action.setChecked(False)
            self.window.statusBar().showMessage("BlackHole 2ch fehlt: einmal mit Administratorrechten installieren und Mac neu starten", 10000)
            return
        self.settings.setValue("broadcastTrinity", enabled)
        self.settings.sync()
        if enabled:
            self.window.claim_speaker()
        self.window.statusBar().showMessage(
            "Trinity und Dein Mikrofon liegen auf BlackHole 2ch; dieses Gerät in Teams/OBS als Mikrofon auswählen"
            if enabled else "Trinity-Ausgabe nach Teams/OBS ausgeschaltet", 10000,
        )

    def _poll_status(self):
        while not self._poll_stop.is_set():
            try:
                microphone = self.window.remote.get_audio_input()
                speaker = self.window.remote.get_speaker()
                mode = self.window.remote.get_mode()
                self._status_bus.updated.emit(microphone, speaker, mode)
            except Exception:
                self._status_bus.updated.emit({}, {}, {})
            self._poll_stop.wait(1.0)

    def set_microphone(self, enabled):
        if enabled:
            self.window.claim_microphone()
        else:
            self.window.release_microphone()

    def _apply_status(self, microphone, speaker, mode=None):
        if mode:
            self.lecture_action.setChecked(mode.get("mode") == "lecture")
            self.office_action.setChecked(mode.get("mode") == "office")
        input_here = microphone.get("device_id") == self.window._device_id
        output_here = speaker.get("device_id") == self.window._device_id
        self.input_action.setChecked(input_here)
        self.output_action.setChecked(output_here)
        active = input_here or output_here
        if active != self.audio_active:
            self.audio_active = active
            self.icon.setIcon(eyes_icon(audio_active=active, dictating=self.dictating))
            self.face.update()
        status = ("Mikrofon hier" if input_here else "Mikrofon anderswo") + " · " + (
            "Ausgabe hier" if output_here else "Ausgabe anderswo")
        self.icon.setToolTip(f"Trinity · {status}")

    def stop(self):
        self._poll_stop.set()
        self.face.hide_face()
        self.icon.hide()

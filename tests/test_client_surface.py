import os
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QWidget

import core.client_surface as surface
from core.client_surface import ClientTray


def test_client_tray_keeps_microphone_and_output_independent(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(QSystemTrayIcon, "isSystemTrayAvailable", lambda: False)
    monkeypatch.setattr(surface, "QSettings", lambda *_args: QSettings(str(tmp_path / "surface.ini"), QSettings.IniFormat))
    window = QWidget()
    window._device_id = "desktop:privat:mac"
    window.remote = Mock()
    window.remote.get_audio_input.return_value = {"device_id": "desktop:privat:mac"}
    window.remote.get_speaker.return_value = {"device_id": "companion:ipad"}
    for name in ("open_companion", "claim_microphone", "claim_speaker", "release_microphone",
                 "mute_speaker", "open_view", "open_settings", "ask_about_active_window",
                 "remember_foreground_app", "set_runtime_mode", "set_window_sharing",
                 "insert_last_answer", "set_debug_terminal", "set_dictation_from_menu"):
        setattr(window, name, Mock())
    tray = ClientTray(window)
    try:
        tray._apply_status(window.remote.get_audio_input(), window.remote.get_speaker())
        assert tray.vision_action.isChecked()
        assert tray.vision_action in tray.menu.actions()
        assert tray.vision_action.text() == "Aktives Fenster erfassen"
        assert "Datenschutz" not in [a.text() for a in tray.menu.actions()]
        tray.vision_action.setChecked(False)
        tray.vision_action.setChecked(True)
        window.set_window_sharing.assert_called_with(True)
        tray.debug_action.trigger()
        window.set_debug_terminal.assert_called_with(True)
        assert "Aktives Fenster mit Trinity besprechen …" not in [a.text() for a in tray.menu.actions()]
        tray.dictation_action.trigger()
        window.set_dictation_from_menu.assert_called_with(True)
        tray.set_dictating(True)
        assert tray.dictation_action.isChecked()
        assert "stoppen" in tray.dictation_action.text()
        tray.dictation_action.trigger()
        window.set_dictation_from_menu.assert_called_with(False)
        tray.set_dictating(False)
        assert not tray.dictation_action.isChecked()
        assert tray.input_action.isChecked()
        assert not tray.output_action.isChecked()
        assert tray.audio_active
        assert "Mac-Mikrofon freigeben" not in [action.text() for action in tray.menu.actions()]
        tray.input_action.trigger()
        window.release_microphone.assert_called_once()
        window.claim_microphone.assert_not_called()
        window.mute_speaker.assert_not_called()
        tray.input_action.trigger()
        window.claim_microphone.assert_called_once()
        window.claim_speaker.assert_not_called()
        tray._apply_status({"device_id": "g2:glasses"}, {"device_id": "desktop:privat:mac"})
        assert not tray.input_action.isChecked()
        assert tray.output_action.isChecked()
        tray.set_floating(True)
        assert tray.face.isVisible()
        tray.set_floating(False)
        assert not tray.face.isVisible()
    finally:
        tray.stop()
        window.close()


def test_dictation_frame_remains_red_when_audio_selection_changes(monkeypatch, tmp_path):
    from core.avatar_tray import eyes_icon
    app = QApplication.instance() or QApplication([])
    plain = eyes_icon(audio_active=True).pixmap(48, 38).toImage()
    framed = eyes_icon(audio_active=True, dictating=True).pixmap(48, 38).toImage()
    def red_pixels(image):
        return sum(image.pixelColor(x, y).alpha() > 100
                   and image.pixelColor(x, y).red() > 220
                   and image.pixelColor(x, y).green() < 100
                   for x in range(image.width()) for y in range(image.height()))
    assert red_pixels(plain) == 0
    assert red_pixels(framed) > 20

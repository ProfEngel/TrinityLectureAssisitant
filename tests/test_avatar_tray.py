import os
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPointF, QSettings, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QWidget

from core.avatar_tray import AvatarTray, eyes_icon
from trinity_app import WebEngineDragFilter


def test_tray_round_trip_persists_preference_and_stops_blinking(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    window = QWidget()
    window.chat_window = QWidget()
    window.content_window = QWidget()
    window.open_chat = Mock()
    window.show_latest_content = Mock()
    window.open_settings = Mock()
    settings = QSettings(str(tmp_path / "avatar.ini"), QSettings.IniFormat)
    tray = AvatarTray(window, Mock(), settings)
    monkeypatch.setattr(QSystemTrayIcon, "isSystemTrayAvailable", lambda: True)
    window.show()
    window.chat_window.show()
    window.content_window.show()
    assert tray.minimize()
    assert not window.isVisible()
    assert not window.chat_window.isVisible()
    assert not window.content_window.isVisible()
    assert settings.value("menuBarOnly", type=bool)
    assert tray.icon.isVisible()
    tray._blink()
    assert tray.closed and tray.open_timer.isActive()
    tray._open_eyes()
    assert not tray.closed and tray.blink_timer.isActive()
    tray.restore()
    assert window.isVisible()
    assert not tray.icon.isVisible()
    assert not settings.value("menuBarOnly", type=bool)
    assert not tray.blink_timer.isActive()
    settings.setValue("menuBarOnly", True)
    tray.apply_startup_mode()
    assert not window.isVisible() and tray.icon.isVisible()
    tray.restore()
    monkeypatch.setattr(QSystemTrayIcon, "isSystemTrayAvailable", lambda: False)
    assert not tray.minimize()
    assert window.isVisible()
    window.close()


def test_double_click_cancels_single_click_chat():
    app = QApplication.instance() or QApplication([])
    window = QWidget()
    window.open_chat_or_bubble = Mock()
    window.tray = Mock()
    event_filter = WebEngineDragFilter(window)

    def mouse(kind):
        return QMouseEvent(kind, QPointF(30, 30), QPointF(100, 100),
                           Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)

    event_filter.eventFilter(window, mouse(QEvent.MouseButtonPress))
    event_filter.eventFilter(window, mouse(QEvent.MouseButtonRelease))
    assert event_filter.click_timer.isActive()
    window.open_chat_or_bubble.assert_not_called()
    assert event_filter.eventFilter(window, mouse(QEvent.MouseButtonDblClick))
    assert not event_filter.click_timer.isActive()
    event_filter.eventFilter(window, mouse(QEvent.MouseButtonRelease))
    assert not event_filter.click_timer.isActive()
    window.tray.minimize.assert_called_once()
    window.open_chat_or_bubble.assert_not_called()


def test_retina_icon_has_distinct_blink_audio_and_theme_frames():
    app = QApplication.instance() or QApplication([])
    opened = eyes_icon().pixmap(48, 38).toImage()
    closed = eyes_icon(closed=True).pixmap(48, 38).toImage()
    active = eyes_icon(audio_active=True).pixmap(48, 38).toImage()
    dark = eyes_icon(light=False, audio_color=False).pixmap(48, 38).toImage()
    assert not opened.isNull()
    assert opened != closed
    assert opened != active
    assert opened != dark
    assert opened.width() == 48 and opened.height() == 38
    assert opened.pixelColor(23, 10).name() == "#e8eeee"
    assert active.pixelColor(23, 10).name() == "#ff9f28"
    assert dark.pixelColor(23, 10).name() == "#0a0a0a"
    assert active.pixelColor(14, 19).name() == "#23b477"
    assert opened.pixelColor(14, 19).name() == "#23b477"
    # Taller face with no reserved dot space unless explicitly requested.
    assert opened.pixelColor(23, 2).name() == "#e8eeee"
    assert opened.pixelColor(23, 35).name() == "#e8eeee"
    dotted = eyes_icon(audio_active=True, show_dot=True).pixmap(60, 38).toImage()
    quiet = eyes_icon(show_dot=True).pixmap(60, 38).toImage()
    assert dotted.pixelColor(55, 19).name() == "#f0a044"
    assert quiet.pixelColor(55, 19).alpha() == 0
    assert dotted.pixelColor(49, 19).alpha() == 0


def test_theme_choice_persists_and_audio_dot_is_independent_of_notifications(tmp_path):
    from core.desktop_audio_activity import mark_audio_active, clear_audio_active
    app = QApplication.instance() or QApplication([])
    window = QWidget()
    window.open_chat = Mock()
    window.show_latest_content = Mock()
    window.open_settings = Mock()
    settings = QSettings(str(tmp_path / "avatar.ini"), QSettings.IniFormat)
    tray = AvatarTray(window, Mock(), settings, home=tmp_path)
    assert tray.light_action.isChecked()
    assert tray.audio_color_action.isChecked()
    assert not tray.dot_action.isChecked()
    assert not tray.light_action.isEnabled()
    tray.audio_color_action.setChecked(False)
    tray.dot_action.setChecked(True)
    assert tray.light_action.isEnabled()
    tray.light_action.setChecked(False)
    assert not tray.light
    assert not settings.value("lightAppearance", type=bool)
    tray.set_notification(True)
    tray.set_state("speaking")  # Animation alone must never create an audio indicator.
    tray.refresh_audio_activity()
    assert not tray.audio_active
    assert "Neu" in tray.result_action.text()
    mark_audio_active(tmp_path, "eve")
    tray.refresh_audio_activity()
    assert tray.audio_active
    clear_audio_active(tmp_path, "eve")
    tray.refresh_audio_activity()
    assert not tray.audio_active
    restored = AvatarTray(window, Mock(), settings, home=tmp_path)
    assert not restored.light_action.isChecked()
    assert not restored.audio_color_action.isChecked()
    assert restored.dot_action.isChecked()
    window.close()

import os
import pytest
pytestmark = pytest.mark.usefixtures("qt_app")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from types import SimpleNamespace
from unittest.mock import Mock
from PySide6.QtWidgets import QApplication, QMainWindow
import trinity_client_app as module


def fake_window(selected=True):
    return SimpleNamespace(
        _device_id="desktop:mac", _textedit_dictating=False, _textedit_target=None,
        _textedit_foreground_target=Mock(return_value=(42, 123)),
        remote=SimpleNamespace(get_audio_input=lambda: {"device_id": "desktop:mac" if selected else "ipad"}),
        statusBar=lambda: Mock(), _say_textedit=Mock(),
        set_window_sharing=Mock(),
    )


def test_start_stop_uses_verified_textedit_and_same_voice_path(monkeypatch):
    window = fake_window()
    monkeypatch.setattr(module, "accessibility_available", lambda: True)
    monkeypatch.setattr(module, "ax_trusted", lambda: True)
    monkeypatch.setattr(module, "foreground_pid", lambda: 42)
    monkeypatch.setattr(module, "focus_diagnostics", lambda: {})
    monkeypatch.setattr(module, "inspect_textedit", lambda: {"text": "", "selection_start": 0, "selection_length": 0})
    module.ClientWindow._handle_textedit_transcript(window, "Trinity, ich diktiere jetzt")
    assert window._textedit_dictating
    assert window._textedit_draft.pid == 42
    window.set_window_sharing.assert_called_with(True)
    window._say_textedit.assert_called_with("Diktat gestartet.")
    module.ClientWindow._handle_textedit_transcript(window, "Trinity, Diktat beenden")
    assert not window._textedit_dictating
    assert window._textedit_target is None


def test_start_rejected_when_other_device_owns_microphone():
    window = fake_window(selected=False)
    module.ClientWindow._handle_textedit_transcript(window, "Trinity, ich diktiere jetzt")
    assert not window._textedit_dictating
    window._textedit_foreground_target.assert_not_called()


def test_missing_permission_requests_access_in_actual_trinity_process(monkeypatch):
    window = fake_window()
    monkeypatch.setattr(module, "accessibility_available", lambda **_kwargs: True)
    monkeypatch.setattr(module, "ax_trusted", lambda: False)
    monkeypatch.setattr(module, "focus_diagnostics", lambda: {"trusted": False})
    request = Mock(return_value=False)
    monkeypatch.setattr(module, "request_ax_access", request)
    module.ClientWindow._handle_textedit_transcript(window, "Trinity, ich diktiere jetzt")
    request.assert_called_once()
    assert not window._textedit_dictating
    assert "Bedienungshilfen" in window._say_textedit.call_args.args[0]


def test_no_target_does_not_claim_missing_permission(monkeypatch):
    window = fake_window()
    window._textedit_foreground_target.return_value = None
    monkeypatch.setattr(module, "accessibility_available", lambda: True)
    monkeypatch.setattr(module, "ax_trusted", lambda: True)
    monkeypatch.setattr(module, "focus_diagnostics", lambda: {})
    module.ClientWindow._handle_textedit_transcript(window, "Trinity, ich diktiere jetzt")
    assert "Bedienungshilfen" not in window._say_textedit.call_args.args[0]
    assert "Textfeld" in window._say_textedit.call_args.args[0]


def test_window_capture_command_is_not_inserted_as_dictated_prose():
    window = fake_window()
    window._textedit_dictating = True
    window._apply_textedit_edit = Mock()
    module.ClientWindow._handle_textedit_transcript(window, "Trinity, Fenstererfassung ausschalten")
    window.set_window_sharing.assert_called_with(False)
    window._apply_textedit_edit.assert_not_called()
    assert window._textedit_dictating


def test_every_dictation_state_change_updates_tray():
    app = QApplication.instance() or QApplication([])
    window = module.ClientWindow.__new__(module.ClientWindow)
    QMainWindow.__init__(window)
    window.tray = Mock()
    window._vision_bus = module._VisionBus(window)
    window._vision_bus.dictation_changed.connect(window._sync_dictation_indicator)
    window._textedit_dictating = True
    window.tray.set_dictating.assert_called_with(True)
    window._textedit_dictating = False
    window.tray.set_dictating.assert_called_with(False)
    window.deleteLater()


def test_menu_start_keeps_original_window_and_waits_for_focus(monkeypatch):
    import sys
    window = SimpleNamespace(_last_external_pid=42, _last_external_window_id=99,
        _handle_textedit_transcript=Mock(), statusBar=lambda: Mock(), _sync_dictation_indicator=Mock())
    callbacks = []
    monkeypatch.setattr(module.QTimer, "singleShot", lambda _delay, callback: callbacks.append(callback))
    app = SimpleNamespace(activateWithOptions_=Mock(return_value=True))
    monkeypatch.setitem(sys.modules, "AppKit", SimpleNamespace(
        NSRunningApplication=SimpleNamespace(runningApplicationWithProcessIdentifier_=lambda pid: app if pid == 42 else None),
        NSApplicationActivateIgnoringOtherApps=1))
    checks = Mock(side_effect=[False, True])
    monkeypatch.setattr(module, "target_still_selected", checks)
    module.ClientWindow.set_dictation_from_menu(window, True)
    window._last_external_pid = 100  # The menu must not replace the captured target.
    callbacks.pop(0)()
    callbacks.pop(0)()
    window._handle_textedit_transcript.assert_not_called()
    callbacks.pop(0)()
    window._handle_textedit_transcript.assert_called_once_with("Trinity, ich diktiere jetzt")
    checks.assert_called_with(42, 99)


def test_summary_is_inserted_with_correct_edit_action_and_bound_draft():
    draft = object()
    window = SimpleNamespace(_textedit_draft=draft, _apply_textedit_edit=Mock(), statusBar=lambda: Mock())
    module.ClientWindow._apply_textedit_generation(window, "summarize", "Kurze Fassung", draft)
    window._apply_textedit_edit.assert_called_once_with("summary", "Kurze Fassung")
    window._apply_textedit_edit.reset_mock()
    module.ClientWindow._apply_textedit_generation(window, "revise", "Alte Antwort", object())
    window._apply_textedit_edit.assert_not_called()


def test_fast_server_response_is_not_lost_before_request_ack():
    import threading
    draft = object()
    pending = {"kind": "revise", "request_id": "", "draft": draft}
    window = SimpleNamespace(_textedit_request=pending, _textedit_request_lock=threading.Lock(),
        _textedit_early_responses={}, _vision_bus=SimpleNamespace(draft_ready=Mock()))
    event = {"role": "assistant", "source": "desktop-textedit", "request_id": "one", "text": "Bessere Fassung"}
    module.ClientWindow._handle_textedit_response(window, event)
    window._vision_bus.draft_ready.emit.assert_not_called()
    assert window._textedit_early_responses["one"] is event
    pending["request_id"] = "one"
    module.ClientWindow._handle_textedit_response(window, window._textedit_early_responses.pop("one"))
    window._vision_bus.draft_ready.emit.assert_called_once_with("revise", "Bessere Fassung", draft)
    assert window._textedit_request is None


def test_existing_selection_can_be_rewritten_without_changing_surrounding_text(monkeypatch):
    import threading
    snapshot = {"pid": 42, "text": "Vorher. Mein Text. Danach.", "selection_start": 8, "selection_length": 10}
    window = SimpleNamespace(_textedit_dictating=False, _textedit_draft=None,
        _textedit_foreground_target=lambda: (42, 99), _textedit_request=None,
        _textedit_request_lock=threading.Lock(), _textedit_early_responses={},
        _say_textedit=Mock(), statusBar=lambda: Mock(),
        remote=SimpleNamespace(send_message=Mock(return_value={"request_id": "one"})),
        _vision_bus=SimpleNamespace(draft_error=Mock()))
    monkeypatch.setattr(module, "inspect_textedit", lambda: snapshot)
    monkeypatch.setattr(module, "target_still_selected", lambda *_: True)
    monkeypatch.setattr(module.threading, "Thread", lambda **kwargs: SimpleNamespace(start=kwargs["target"]))
    module.ClientWindow._request_textedit_generation(window, "revise")
    assert window._textedit_draft.original == "Mein Text."
    assert window._textedit_draft.document == snapshot["text"]
    prompt = window.remote.send_message.call_args.args[0]
    assert prompt.endswith("Mein Text.")
    assert "Vorher." not in prompt
    assert "Danach." not in prompt
    assert "englische Fachbegriffe" in prompt


def test_open_app_stops_dictation_and_uses_bundle_not_arbitrary_shell(monkeypatch):
    window = fake_window()
    window._textedit_dictating = True
    run = Mock(return_value=SimpleNamespace(returncode=0))
    monkeypatch.setattr(module.subprocess, "run", run)
    module.ClientWindow._handle_textedit_transcript(window, "Trinity, öffne Mail")
    assert not window._textedit_dictating
    assert run.call_args.args[0] == ["/usr/bin/open", "-b", "com.apple.mail"]
    window._say_textedit.assert_called_with("Mail geöffnet.")

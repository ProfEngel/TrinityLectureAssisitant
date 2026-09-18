import os

from core.desktop_audio_activity import (
    clear_audio_active, desktop_audio_active, mark_audio_active,
)


def test_indicator_tracks_open_audio_sources_and_disappears_after_stop(tmp_path):
    assert not desktop_audio_active(tmp_path)
    mark_audio_active(tmp_path, "eve")
    assert desktop_audio_active(tmp_path)
    mark_audio_active(tmp_path, "microphone")
    clear_audio_active(tmp_path, "eve")
    assert desktop_audio_active(tmp_path)
    clear_audio_active(tmp_path, "microphone")
    assert not desktop_audio_active(tmp_path)


def test_crashed_process_marker_does_not_leave_indicator_on(tmp_path, monkeypatch):
    mark_audio_active(tmp_path, "speech", 987654)

    def no_process(pid):
        assert pid == 987654
        raise ProcessLookupError()

    monkeypatch.setattr("core.desktop_audio_activity._process_is_alive", no_process)
    assert not desktop_audio_active(tmp_path)


def test_invalid_process_ids_are_never_signalled(tmp_path, monkeypatch):
    path = tmp_path / "TrinityRuntime" / "voice" / "desktop_eve_audio.ready"
    path.parent.mkdir(parents=True)
    def unexpected_signal(*args):
        raise AssertionError("invalid PID")
    monkeypatch.setattr(os, "kill", unexpected_signal)
    for value in ("", "garbage", "-1", "0", "1"):
        path.write_text(value)
        assert not desktop_audio_active(tmp_path)


def test_windows_probe_never_sends_a_signal(monkeypatch):
    from core import desktop_audio_activity as activity
    monkeypatch.setattr(activity.sys, "platform", "win32")
    monkeypatch.setattr(activity, "_windows_process_is_alive", lambda pid: pid == 123)
    def forbidden(*args):
        raise AssertionError("Windows must never use os.kill for a liveness probe")
    monkeypatch.setattr(os, "kill", forbidden)
    assert activity._process_is_alive(123)
    assert not activity._process_is_alive(456)

import io

from PIL import Image

import core.mac_window_vision as vision
from core.mac_window_vision import choose_window


def test_selects_frontmost_sizable_window_from_requested_app():
    windows = [
        {"kCGWindowOwnerPID": 41, "kCGWindowLayer": 0,
         "kCGWindowBounds": {"Width": 700, "Height": 500}},
        {"kCGWindowOwnerPID": 42, "kCGWindowLayer": 1,
         "kCGWindowBounds": {"Width": 700, "Height": 500}},
        {"kCGWindowOwnerPID": 42, "kCGWindowLayer": 0,
         "kCGWindowBounds": {"Width": 800, "Height": 600}},
    ]
    assert choose_window(windows, 42) is windows[2]
    assert choose_window(windows, None) is None


def test_jpeg_capture_is_bounded_and_removes_temporary_png(tmp_path, monkeypatch):
    png = tmp_path / "window.png"
    Image.new("RGB", (2400, 1200), "white").save(png)
    monkeypatch.setattr(vision, "capture_window", lambda _pid: (png, "Excel"))
    encoded, title = vision.capture_window_jpeg(42)
    assert title == "Excel"
    assert encoded.startswith(b"\xff\xd8\xff")
    with Image.open(io.BytesIO(encoded)) as image:
        assert max(image.size) <= 1600
    assert not png.exists()


def test_insert_requires_the_same_frontmost_window(monkeypatch):
    monkeypatch.setattr(vision, "foreground_pid", lambda: 42)
    monkeypatch.setattr(vision, "window_descriptor", lambda _pid: {"kCGWindowNumber": 99})
    assert vision.target_still_selected(42, 99)
    assert not vision.target_still_selected(42, 98)
    monkeypatch.setattr(vision, "foreground_pid", lambda: 43)
    assert not vision.target_still_selected(42, 99)

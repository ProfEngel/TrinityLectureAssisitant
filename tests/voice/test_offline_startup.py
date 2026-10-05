import sys
import types
from core.voice.offline_startup import install_cached_vad_loader


def test_vad_cached_start_does_not_probe_github(tmp_path, monkeypatch):
    cached = tmp_path / 'snakers4_silero-vad_master'
    cached.mkdir()
    (cached / 'hubconf.py').touch()
    calls = []
    hub = types.SimpleNamespace(get_dir=lambda: str(tmp_path),
        load=lambda *a, **kw: calls.append((a, kw)))
    monkeypatch.setitem(sys.modules, 'torch', types.SimpleNamespace(hub=hub))
    install_cached_vad_loader()
    install_cached_vad_loader()
    hub.load('snakers4/silero-vad', 'silero_vad', trust_repo=True)
    assert calls == [((str(cached), 'silero_vad'), {'trust_repo': True, 'source': 'local'})]


def test_first_install_and_other_models_are_unchanged(tmp_path, monkeypatch):
    calls = []
    hub = types.SimpleNamespace(get_dir=lambda: str(tmp_path),
        load=lambda *a, **kw: calls.append((a, kw)))
    monkeypatch.setitem(sys.modules, 'torch', types.SimpleNamespace(hub=hub))
    install_cached_vad_loader()
    hub.load('snakers4/silero-vad', 'silero_vad')
    hub.load('other/model', 'other')
    assert calls == [(('snakers4/silero-vad', 'silero_vad'), {}), (('other/model', 'other'), {})]

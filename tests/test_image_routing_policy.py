from types import SimpleNamespace

from agents.comfyui_agent import script as comfy
from agents.image_agent import script as external


def test_normal_request_only_matches_comfy():
    query = 'Trinity, erstelle ein Bild zu neuronalen Netzen.'
    assert comfy.can_handle(query)
    assert not external.can_handle(query)


def test_explicit_external_request_only_matches_external():
    query = 'Trinity, erstelle ein externes Bild zu neuronalen Netzen.'
    assert not comfy.can_handle(query)
    assert external.can_handle(query)


def test_unavailable_comfy_does_not_generate_or_use_cloud(monkeypatch):
    called = []
    monkeypatch.setattr(comfy, '_ping_server', lambda url: called.append(url) or False)
    monkeypatch.setattr(comfy, '_queue_prompt', lambda *_: (_ for _ in ()).throw(AssertionError('No job')))
    monkeypatch.setattr(external, '_generate_image_fal', lambda *_: (_ for _ in ()).throw(AssertionError('No cloud')))
    brain = SimpleNamespace(comfyui_enabled=True, comfyui_url='http://local:8188')
    result = comfy.execute('Erstelle ein Bild zu KI.', {'brain': brain})
    assert called == ['http://local:8188']
    assert not result['has_payload']
    assert 'kein externer Anbieter' in result['search_context']


def test_direct_external_execution_also_requires_authorization(monkeypatch):
    monkeypatch.setattr(external, '_generate_image_fal', lambda *_: (_ for _ in ()).throw(AssertionError('No cloud')))
    result = external.execute('Erstelle ein Bild zu KI.', {'brain': SimpleNamespace()})
    assert not result['has_payload']
    assert 'ohne ausdrücklichen Wunsch' in result['search_context']

import json
from types import SimpleNamespace

import pytest
from agents.comfyui_agent import script
from agents.comfyui_agent.yue_music import extract_params, inject_inputs


@pytest.mark.parametrize('query', ['Trinity, mach uns ein Fahrstuhlmusik-Lied',
    'Erstelle einen Rocksong der 80er', 'Erstelle ein typisches Drake-Lied'])
def test_creation_requests_route_to_music(query):
    assert script.can_handle_song(query)


def test_questions_about_music_are_not_creation():
    assert not script.can_handle_song('Wie funktioniert Musik?')


def test_short_demo_and_instrumental_enforced():
    brain = SimpleNamespace(ask_llm=lambda *_: json.dumps({
        'tags': 'gentle lounge jazz', 'lyrics': 'words', 'duration': 250, 'bpm': 95}))
    params = extract_params('Mach ein Fahrstuhlmusik-Lied', brain)
    assert params['duration'] == 55
    assert params['lyrics'] == '[Instrumental]'
    workflow = script._load_workflow('audio_yue2_text2music_API.json')
    modified = inject_inputs(workflow, params)
    assert modified['33:25']['inputs']['max_duration'] == 55
    assert modified['33:5']['inputs']['seconds'] == 55
    assert modified['33:25']['inputs']['style'].startswith('gentle lounge jazz')
    assert modified['33:24']['inputs']['lyrics'] == '[Instrumental]'
    assert workflow['33:25']['inputs']['max_duration'] == 250


def test_bad_brief_rejected_instead_of_wrong_song():
    with pytest.raises(ValueError):
        extract_params('Rock', SimpleNamespace(ask_llm=lambda *_: 'not json'))


def test_audio_download_uses_returned_location(tmp_path, monkeypatch):
    seen = []
    def get(url, **kwargs):
        seen.append(kwargs['params'])
        return SimpleNamespace(status_code=200, content=b'audio')
    monkeypatch.setattr(script.requests, 'get', get)
    assert script._download_audio('http://comfy', {'filename': 'test.mp3',
        'subfolder': 'audio/yue', 'type': 'output'}, str(tmp_path))
    assert seen[0]['subfolder'] == 'audio/yue'
    assert script._download_audio('http://comfy', {'filename': '../evil'}, str(tmp_path)) is None


def test_audio_payload_has_player_and_escapes_lyrics():
    result = script._build_audio_payload('/tmp/test.mp3', 'Demo', {
        'tags': '<script>', 'lyrics': '<script>', 'engine': 'YuE2'})
    assert '<audio controls' in result and 'YuE2' in result
    assert '<script>' not in result

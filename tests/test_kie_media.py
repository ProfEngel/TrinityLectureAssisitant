import json
import types
import pytest
from agents.kie_media_agent import script
from core.brain import TrinityBrain


def test_image_parameters_are_fixed():
    task = script.image_task('Eine Infografik')
    assert task['model'] == 'gpt-image-2-5-flare-text-to-image'
    assert task['input']['resolution'] == '2K'
    assert task['input']['aspect_ratio'] == '16:9'
    assert 'Deutsch' in task['input']['prompt']


def test_music_parameters_are_v6_short_original_song():
    task = script.music_task({'style': '80s rock', 'lyrics': '[Verse] Eigener Text', 'duration': 200})
    assert task['model'] == 'ai-music-api/generate'
    assert task['input']['model'] == 'V6'
    assert task['input']['custom_mode'] is True
    assert task['input']['duration'] == 55
    assert task['input']['lyrics'] == '[Verse] Eigener Text'


def test_instrumental_has_no_lyrics():
    task = script.music_task({'style': 'lounge', 'lyrics': 'ignored', 'instrumental': True})
    assert task['input']['lyrics'] == ''


def test_music_result_objects_are_supported():
    data = {'sunoData': [{'audio_url': 'https://cdn.example/one.mp3'},
                         {'audioUrl': 'https://cdn.example/two.mp3'}]}
    assert script._result_urls(data) == ['https://cdn.example/one.mp3', 'https://cdn.example/two.mp3']


def test_fallback_only_after_safe_failure(tmp_path, monkeypatch):
    from agents.comfyui_agent import script as comfy
    brain = TrinityBrain.__new__(TrinityBrain)
    brain.config_path = str(tmp_path / 'core/config.json')
    brain.config = {'media_generation': {'comfyui_fallback': True}}
    monkeypatch.setattr('core.brain.diagnostic', lambda *a: None)
    calls = []
    monkeypatch.setattr(comfy, 'execute', lambda *a, **kw: (calls.append('comfy'), {'has_payload': True})[1])
    def reject(query, context=None): return {'has_payload': False, 'fallback_safe': True}
    reject.__module__ = 'agents.kie_media_agent'
    assert brain._run_media_skill(reject, 'Erstelle ein Bild', {})['has_payload']
    def pending(query, context=None): return {'has_payload': False, 'fallback_safe': False}
    pending.__module__ = reject.__module__
    assert not brain._run_media_skill(pending, 'Erstelle ein Bild', {})['has_payload']
    assert calls == ['comfy']


def test_shared_routing_uses_only_kie():
    brain = TrinityBrain.__new__(TrinityBrain)
    brain.media_provider = 'kie'
    for name in ('agents.comfyui_agent', 'agents.image_agent', 'agents.sandbox_agent'):
        other = types.SimpleNamespace(__name__=name, can_handle=lambda q: True, can_handle_song=lambda q: True)
        assert not brain._skill_can_handle(other, 'Erstelle ein Diagramm')
        assert not brain._skill_can_handle_song(other, 'Erstelle ein Lied')
    assert brain._skill_can_handle(script, 'Erstelle ein Diagramm')
    assert brain._skill_can_handle_song(script, 'Erstelle ein Lied')
    assert not script.can_handle_song('Erstelle ein Bild zum Thema Musik')
    assert not script.can_handle_song('Wir bauen dir etwas, damit du Bilder und Musik machen kannst. Was hältst du davon, Trinity?')
    local = types.SimpleNamespace(__name__='agents.comfyui_agent', can_handle=lambda q: True, can_handle_song=lambda q: True)
    assert brain._skill_can_handle(local, 'Erstelle ein lokales Schaubild')
    assert not brain._skill_can_handle(script, 'Erstelle ein lokales Schaubild')
    assert brain._skill_can_handle_song(local, 'Erstelle ein lokales Lied')
    assert not brain._skill_can_handle_song(script, 'Erstelle ein lokales Lied')


def test_unified_job_protocol(monkeypatch):
    calls = []
    class Response:
        def __init__(self, body): self.body = body
        def raise_for_status(self): pass
        def json(self): return self.body
    monkeypatch.setattr(script.requests, 'post', lambda url, **kw: (calls.append((url, kw)), Response({'code': 200, 'data': {'taskId': 'test-job'}}))[1])
    monkeypatch.setattr(script.requests, 'get', lambda url, **kw: Response({'code': 200, 'data': {
        'state': 'success', 'resultJson': json.dumps({'resultUrls': ['https://cdn.example/song.mp3']})}}))
    job, urls = script.submit_and_wait(script.music_task({'style': 'lounge', 'instrumental': True}), 'test-secret')
    assert job == 'test-job'
    assert urls == ['https://cdn.example/song.mp3']
    assert calls[0][0].endswith('/jobs/createTask')
    assert calls[0][1]['headers']['Authorization'] == 'Bearer test-secret'


def test_rejected_job_is_never_retried(monkeypatch):
    calls = []
    response = types.SimpleNamespace(raise_for_status=lambda: None, json=lambda: {'code': 401})
    monkeypatch.setattr(script.requests, 'post', lambda *a, **kw: (calls.append(1), response)[1])
    with pytest.raises(RuntimeError, match='401'):
        script.submit_and_wait(script.image_task('Test'), 'test-secret')
    assert calls == [1]


def test_pending_status_never_allows_fallback(monkeypatch):
    response = types.SimpleNamespace(raise_for_status=lambda: None, json=lambda: {'code': 200, 'data': {'taskId': 'pending-job'}})
    monkeypatch.setattr(script.requests, 'post', lambda *a, **kw: response)
    monkeypatch.setattr(script.requests, 'get', lambda *a, **kw: types.SimpleNamespace(raise_for_status=lambda: None, json=lambda: {'code': 500}))
    with pytest.raises(script.KieJobUncertain):
        script.submit_and_wait(script.image_task('Test'), 'test-secret')


def test_background_job_is_once_and_publishes_single_result(tmp_path, monkeypatch):
    import threading
    import time
    from core import media_jobs
    from core.chat_protocol import load_chat_events
    gate = threading.Event()
    calls = []
    class Brain:
        def _run_media_skill(self, execute, query, context):
            calls.append(query)
            gate.wait(2)
            return {'has_payload': True, 'html_payload': '<img src="test.png">', 'direct_answer': 'Fertig'}
    query = 'Erstelle ein Diagramm'
    def execute(query, context=None): pass
    context = {'brain': Brain()}
    first = media_jobs.start_media_job(tmp_path, query, execute, context)
    second = media_jobs.start_media_job(tmp_path, query, execute, context)
    assert not first['has_payload'] and not second['has_payload']
    assert 'bereits gestartet' in second['direct_answer']
    gate.set()
    history = media_jobs.tenant_history_path(tmp_path)
    for _ in range(300):
        events = load_chat_events(history)
        if events: break
        time.sleep(.01)
    assert len(calls) == 1 and len(events) == 1
    assert events[0]['payload_html'] == '<img src="test.png">'
    third = media_jobs.start_media_job(tmp_path, query, execute, context)
    assert not third['has_payload']
    assert len(calls) == 1


def test_media_workers_do_not_compete_with_each_other(tmp_path):
    import threading
    import time
    from core import media_jobs
    from core.chat_protocol import load_chat_events
    first_started = threading.Event()
    release = threading.Event()
    calls = []
    class Brain:
        def _run_media_skill(self, execute, query, context):
            calls.append(query)
            first_started.set()
            release.wait(2)
            return {'has_payload': True, 'html_payload': '<img src="test.png">'}
    def execute(query, context=None): pass
    context = {'brain': Brain()}
    media_jobs.start_media_job(tmp_path, 'Erstes Bild', execute, context)
    assert first_started.wait(1)
    media_jobs.start_media_job(tmp_path, 'Zweites Bild', execute, context)
    time.sleep(.05)
    assert len(calls) == 1
    release.set()
    history = media_jobs.tenant_history_path(tmp_path)
    for _ in range(300):
        if len(load_chat_events(history)) == 2:
            break
        time.sleep(.01)
    assert len(load_chat_events(history)) == 2
    assert calls == ['Erstes Bild', 'Zweites Bild']


def test_accepted_media_job_does_not_inherit_cancelled_voice_scope(tmp_path):
    import threading
    from core import media_jobs
    from core.voice.request_scope import request_scope, check_cancelled
    cancelled, release, finished = threading.Event(), threading.Event(), threading.Event()
    class Brain:
        def _run_media_skill(self, execute, query, context):
            assert release.wait(3)
            check_cancelled()
            finished.set()
            return {'has_payload': True, 'html_payload': '<img src="test.png">'}
    def execute(query, context=None): pass
    with request_scope(cancelled.is_set):
        media_jobs.start_media_job(tmp_path, 'Accepted image', execute, {'brain': Brain()})
    cancelled.set()
    release.set()
    assert finished.wait(3)

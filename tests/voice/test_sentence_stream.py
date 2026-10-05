import json
import threading
import io
from urllib.request import Request, urlopen

import pytest

from voice.sentence_stream import StreamCancelled, stream_sentences
from voice.conversation.trinity_backend import TrinityConversationHTTPServer
from voice.conversation.trinity_backend import TrinityConversationBackend
from test_voice_backend_http import FakeBackend, free_port


class Response:
    def __init__(self, chunks, done=True):
        self.chunks, self.done = chunks, done

    def iter_lines(self, **kwargs):
        for content in self.chunks:
            yield 'data: ' + json.dumps({'choices': [{'delta': {'content': content}}]})
        if self.done:
            yield 'data: [DONE]'


def test_utf8_sse_with_latin1_http_default_and_split_multibyte_characters():
    import requests
    response = requests.Response()
    response.status_code = 200
    response.headers['Content-Type'] = 'text/event-stream'
    response.encoding = 'ISO-8859-1'  # requests' default for text/* without charset
    sentence = 'Für größere Übungen heißt es: Grüße, äußere Größe und süß.'
    event = {'choices': [{'delta': {'content': sentence}}]}
    response.raw = io.BytesIO(('data: ' + json.dumps(event, ensure_ascii=False) + '\n\ndata: [DONE]\n\n').encode('utf-8'))
    spoken = []
    assert stream_sentences(response, spoken.append) == sentence
    assert spoken == [sentence]


def test_incremental_visible_sentences():
    spoken = []
    answer = stream_sentences(Response(['<thi', 'nk>Geheim.</think>', 'Hallo Welt.', ' Zweiter Satz.', ' Ende']), spoken.append)
    assert spoken == ['Hallo Welt.', 'Zweiter Satz.', 'Ende']
    assert answer == 'Hallo Welt. Zweiter Satz. Ende'


def test_abbreviations_do_not_hold_back_following_sentences():
    spoken = []
    stream_sentences(Response(['Dr. Smith nennt z. B. zwei Ursachen. ', 'Eine ist wichtig. ', 'Ende.']), spoken.append)
    assert spoken == ['Dr. Smith nennt z. B. zwei Ursachen.', 'Eine ist wichtig.', 'Ende.']


def test_no_reasoning_field_fallback_or_code():
    spoken = []
    stream_sentences(Response(['```python\nsecret.\n```', 'Hallo.']), spoken.append)
    assert spoken == ['Hallo.']


def test_incomplete_stream_and_cancellation():
    with pytest.raises(ValueError, match='Incomplete'):
        stream_sentences(Response(['Hallo'], done=False), lambda _: None)
    with pytest.raises(StreamCancelled):
        stream_sentences(Response(['Hallo.']), lambda _: None, lambda: True)


def test_http_first_sentence_before_generation_finishes():
    release = threading.Event()
    class StreamingBackend(FakeBackend):
        def respond_stream(self, text, *, turn_id=''):
            yield 'Erster Satz.'
            assert release.wait(3)
            yield 'Zweiter Satz.'
    port = free_port()
    server = TrinityConversationHTTPServer(StreamingBackend(), '127.0.0.1', port, '')
    server.start()
    try:
        data = json.dumps({'stream': True, 'messages': [{'role': 'user', 'content': 'Hallo'}]}).encode()
        with urlopen(Request(f'http://127.0.0.1:{port}/v1/chat/completions', data=data), timeout=2) as response:
            first = response.readline().decode()
            assert 'Erster Satz.' in first
            assert not release.is_set()
            release.set()
            assert '[DONE]' in response.read().decode()
    finally:
        release.set()
        server.stop()


def test_backend_stream_persists_complete_answer_once(tmp_path, monkeypatch):
    (tmp_path / 'core').mkdir()
    (tmp_path / 'core/config.json').write_text(json.dumps({'system': {'voice_sentence_streaming': True}}))
    backend = TrinityConversationBackend(tmp_path)
    monkeypatch.setattr(backend, '_desktop_microphone_selected', lambda: False)
    saved = []
    monkeypatch.setattr(backend, '_append_chat_events', lambda *args: saved.append(args))
    class Brain:
        def ask(self, *args, **kwargs):
            kwargs['sentence_callback']('Hallo.')
            kwargs['sentence_callback']('Zweiter Satz.')
            return 'Hallo. Zweiter Satz.', False
    monkeypatch.setattr(backend, '_ensure_brain', lambda: Brain())
    assert list(backend.respond_stream('Hallo')) == ['Hallo.', 'Zweiter Satz.']
    assert len(saved) == 1
    assert saved[0][1] == 'Hallo. Zweiter Satz.'


def test_closed_stream_cancels_producer_without_memory_write(tmp_path, monkeypatch):
    (tmp_path / 'core').mkdir()
    (tmp_path / 'core/config.json').write_text(json.dumps({'system': {'voice_sentence_streaming': True}}))
    backend = TrinityConversationBackend(tmp_path)
    monkeypatch.setattr(backend, '_desktop_microphone_selected', lambda: False)
    saved, release, stopped = [], threading.Event(), threading.Event()
    monkeypatch.setattr(backend, '_append_chat_events', lambda *args: saved.append(args))
    class Brain:
        def ask(self, *args, **kwargs):
            try:
                kwargs['sentence_callback']('Erster Satz.')
                assert release.wait(2)
                kwargs['sentence_callback']('Dieser Satz darf nicht mehr erscheinen.')
                return 'Falsche vollständige Antwort', False
            finally:
                stopped.set()
    monkeypatch.setattr(backend, '_ensure_brain', lambda: Brain())
    stream = backend.respond_stream('Hallo')
    assert next(stream) == 'Erster Satz.'
    stream.close()
    release.set()
    assert stopped.wait(2)
    assert saved == []


def test_http_disconnect_before_first_sentence_stops_work_without_memory(tmp_path, monkeypatch):
    import socket
    import time
    from core.voice.request_scope import check_cancelled
    (tmp_path / 'core').mkdir()
    (tmp_path / 'core/config.json').write_text(json.dumps({'system': {'voice_sentence_streaming': True}}))
    backend = TrinityConversationBackend(tmp_path)
    monkeypatch.setattr(backend, '_desktop_microphone_selected', lambda: False)
    started, stopped = threading.Event(), threading.Event()
    saved = []
    monkeypatch.setattr(backend, '_append_chat_events', lambda *args: saved.append(args))
    class Brain:
        def ask(self, *args, **kwargs):
            started.set()
            try:
                deadline = time.monotonic() + 4
                while time.monotonic() < deadline:
                    check_cancelled()
                    time.sleep(0.02)
                return 'Must not persist after disconnect', False
            finally:
                stopped.set()
    monkeypatch.setattr(backend, '_ensure_brain', lambda: Brain())
    port = free_port()
    server = TrinityConversationHTTPServer(backend, '127.0.0.1', port, '')
    server.start()
    sock = socket.create_connection(('127.0.0.1', port), timeout=2)
    try:
        payload = json.dumps({'stream': True, 'messages': [{'role': 'user', 'content': 'Hallo'}]}).encode()
        sock.sendall(f'POST /v1/chat/completions HTTP/1.1\r\nHost: localhost\r\nContent-Length: {len(payload)}\r\nContent-Type: application/json\r\n\r\n'.encode() + payload)
        assert started.wait(2)
        sock.shutdown(socket.SHUT_RDWR)
        sock.close()
        assert stopped.wait(2)
        assert not saved
    finally:
        sock.close()
        server.stop()


def test_new_request_supersedes_old_inflight_without_stale_memory(tmp_path, monkeypatch):
    import time
    from core.voice.request_scope import check_cancelled
    (tmp_path / 'core').mkdir()
    (tmp_path / 'core/config.json').write_text(json.dumps({'system': {'voice_sentence_streaming': True}}))
    backend = TrinityConversationBackend(tmp_path)
    monkeypatch.setattr(backend, '_desktop_microphone_selected', lambda: False)
    saved, started = [], threading.Event()
    monkeypatch.setattr(backend, '_append_chat_events', lambda *args: saved.append(args))
    class Brain:
        def ask(self, query, *args, **kwargs):
            if query == 'Alt':
                started.set()
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    check_cancelled()
                    time.sleep(0.02)
                pytest.fail('Old request must be interrupted')
            kwargs['sentence_callback']('Neue Antwort.')
            return 'Neue Antwort.', False
    monkeypatch.setattr(backend, '_ensure_brain', lambda: Brain())
    old = []
    worker = threading.Thread(target=lambda: old.extend(backend.respond_stream('Alt')), daemon=True)
    worker.start()
    assert started.wait(2)
    assert [x for x in backend.respond_stream('Neu') if x is not None] == ['Neue Antwort.']
    worker.join(2)
    assert not worker.is_alive()
    assert not [x for x in old if x is not None]
    assert len(saved) == 1 and saved[0][0] == 'Neu'

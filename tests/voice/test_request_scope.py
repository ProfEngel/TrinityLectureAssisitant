import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import requests

from core.voice.request_scope import request_scope, interruptible_response, collect_content, check_cancelled
from core.voice.cancellation import StreamCancelled


@pytest.mark.parametrize("by_deadline", [False, True])
def test_cancellation_interrupts_real_stalled_model_read(by_deadline):
    ready, release, cancel, stopped, reading = [threading.Event() for _ in range(5)]
    errors = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            self.wfile.write(b": ready\n\n")
            self.wfile.flush()
            ready.set()
            release.wait(4)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    serving = threading.Thread(target=server.serve_forever, daemon=True)
    serving.start()
    def work():
        try:
            with request_scope(cancel.is_set, 0.5 if by_deadline else 5):
                with interruptible_response(requests.get(
                    f"http://127.0.0.1:{server.server_port}", stream=True, timeout=(1, 10),
                )) as response:
                    original_lines = response.iter_lines
                    def lines(**kwargs):
                        for line in original_lines(**kwargs):
                            reading.set()
                            yield line
                    response.iter_lines = lines
                    collect_content(response)
        except Exception as exc:
            errors.append(exc)
        finally:
            stopped.set()
    worker = threading.Thread(target=work, daemon=True)
    worker.start()
    try:
        assert ready.wait(2)
        assert reading.wait(2), "Exercise a body read, not just cancellation before reading"
        cancel.set() if not by_deadline else None
        assert stopped.wait(2), "Cancellation must not wait for the 10-second model read timeout"
        assert len(errors) == 1 and isinstance(errors[0], StreamCancelled)
    finally:
        release.set()
        worker.join(2)
        server.shutdown()
        server.server_close()


def test_internal_stream_preserves_code_and_ignores_reasoning():
    class Response:
        def iter_lines(self, **kwargs):
            yield 'data: ' + json.dumps({'choices': [{'delta': {'reasoning_content': 'secret'}}]})
            yield 'data: ' + json.dumps({'choices': [{'delta': {'content': 'print("für")'}}]})
            yield 'data: [DONE]'
    assert collect_content(Response()) == 'print("für")'


def test_cancelled_scope_does_not_leak_into_next_request():
    with pytest.raises(StreamCancelled):
        with request_scope(lambda: True):
            pytest.fail("Must not start stale work")
    check_cancelled()
    with request_scope(lambda: False):
        check_cancelled()


def test_aliases_share_cancellation_identity():
    from voice.sentence_stream import StreamCancelled as legacy
    assert legacy is StreamCancelled

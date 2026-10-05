"""Bound voice requests and interrupt an open model stream on cancellation.

The scope is thread-local through ContextVar. Accepted background media jobs
do not inherit it. Socket shutdown is necessary: Response.close alone can block
behind a buffered read. The guarded urllib3 adapter is tested with real HTTP;
providers without an accessible socket retain their bounded read timeout.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import socket
import threading
import time

from .sentence_stream import StreamCancelled

_current = ContextVar("trinity_voice_request", default=None)


class RequestExpired(StreamCancelled):
    """A bounded request expired without an explicit listener cancellation."""


class RequestScope:
    def __init__(self, cancelled, timeout_seconds):
        self.cancelled = cancelled
        self.deadline = time.monotonic() + timeout_seconds

    def stale(self):
        return self.cancelled() or time.monotonic() >= self.deadline

    def check(self):
        if self.cancelled():
            raise StreamCancelled("Voice request superseded, disconnected or expired")
        if time.monotonic() >= self.deadline:
            raise RequestExpired("Voice response deadline exceeded")


@contextmanager
def request_scope(cancelled, timeout_seconds=45):
    scope = RequestScope(cancelled, timeout_seconds)
    token = _current.set(scope)
    try:
        scope.check()
        yield scope
    finally:
        _current.reset(token)


def current_scope():
    return _current.get()


def check_cancelled():
    scope = current_scope()
    if scope:
        scope.check()


@contextmanager
def interruptible_response(response):
    scope = current_scope()
    finished = threading.Event()
    watcher = None
    if scope:
        try:
            sock = response.raw._fp.fp.raw._sock
        except AttributeError:
            sock = None

        def watch():
            while not finished.wait(0.05):
                if scope.stale():
                    if sock:
                        try:
                            sock.shutdown(socket.SHUT_RDWR)
                        except OSError:
                            pass
                    return

        watcher = threading.Thread(target=watch, name="trinity-model-cancel", daemon=True)
        watcher.start()
    try:
        check_cancelled()
        yield response
        check_cancelled()
    except Exception:
        check_cancelled()  # normalize an interrupted socket read to StreamCancelled
        raise
    finally:
        finished.set()
        response.close()
        if watcher:
            watcher.join(timeout=0.2)


def collect_content(response):
    """Internal tool LLM stream: preserve code; never fall back to reasoning."""
    import json
    response.encoding = "utf-8"
    parts = []
    size = 0
    complete = False
    for line in response.iter_lines(chunk_size=1, decode_unicode=True):
        check_cancelled()
        if not line.startswith("data:"):
            continue
        raw = line[5:].strip()
        if raw == "[DONE]":
            complete = True
            break
        event = json.loads(raw)
        if event.get("error"):
            raise ValueError("Internal model streaming error")
        choices = event.get("choices") or []
        if not choices:
            continue
        part = choices[0].get("delta", {}).get("content") or ""
        parts.append(part)
        size += len(part)
        if size > 65536:
            raise ValueError("Oversized internal model output")
        complete = complete or bool(choices[0].get("finish_reason"))
    check_cancelled()
    if not complete:
        raise ValueError("Incomplete internal model stream")
    return "".join(parts)

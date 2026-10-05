import json
import socket
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from voice.conversation.trinity_backend import READ_ALOUD_PREFIX, TrinityConversationHTTPServer
from voice.interfaces import ConversationBackend


class FakeBackend(ConversationBackend):
    def respond(self, text, *, session_id="", turn_id=""):
        return [f"Antwort auf {text}"]


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def request(port, token=""):
    payload = json.dumps({
        "model": "trinity-core",
        "messages": [{"role": "user", "content": "Hallo"}],
    }).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return Request(
        f"http://127.0.0.1:{port}/v1/chat/completions",
        data=payload,
        headers=headers,
        method="POST",
    )


def test_backend_requires_token_and_returns_openai_shape():
    port = free_port()
    server = TrinityConversationHTTPServer(FakeBackend(), "127.0.0.1", port, "secret")
    server.start()
    try:
        with pytest.raises(HTTPError) as unauthorized:
            urlopen(request(port), timeout=2)
        assert unauthorized.value.code == 401

        with urlopen(request(port, "secret"), timeout=2) as response:
            result = json.loads(response.read().decode("utf-8"))
        assert result["choices"][0]["message"]["content"] == "Antwort auf Hallo"
    finally:
        server.stop()


def test_read_aloud_returns_exact_text_without_running_brain():
    class RecordingBackend(FakeBackend):
        def respond(self, text, *, session_id="", turn_id=""):
            raise AssertionError("Already generated text must not run through the brain")

    port = free_port()
    server = TrinityConversationHTTPServer(RecordingBackend(), "127.0.0.1", port, "secret")
    server.start()
    try:
        payload = json.dumps({
            "model": "trinity-core",
            "messages": [{"role": "user", "content": READ_ALOUD_PREFIX + "Hallo von Eve."}],
        }).encode()
        req = Request(
            f"http://127.0.0.1:{port}/v1/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json", "Authorization": "Bearer secret"},
        )
        with urlopen(req, timeout=2) as response:
            result = json.loads(response.read())
        assert result["choices"][0]["message"]["content"] == "Hallo von Eve."
    finally:
        server.stop()

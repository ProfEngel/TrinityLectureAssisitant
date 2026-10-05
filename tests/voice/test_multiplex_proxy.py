import asyncio
import base64
import json
import socket
import threading
import time
from urllib.request import Request, urlopen

import websockets
from websockets.sync.client import connect

from voice.input_selection import AudioInputSelection
from voice.transport.multiplex_proxy import MultiplexingVoiceRouter


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_one_upstream_routes_separate_microphone_speaker_and_g2(tmp_path):
    config_path = tmp_path / "core" / "config.json"
    config_path.parent.mkdir()
    config_path.write_text(json.dumps({"system": {
        "audio_input": {"kind": "companion", "device_id": "companion:iphone", "label": "iPhone"},
        "speech_output": {"kind": "companion", "device_id": "companion:ipad", "label": "iPad"},
    }}))
    upstream_port, public_port, stt_port = (_free_port() for _ in range(3))
    events = []
    server_loop = asyncio.new_event_loop()
    server_ready = threading.Event()
    server_holder = {}

    async def upstream_handler(websocket):
        await websocket.send(json.dumps({"type": "session.created", "session": {}}))
        async for raw in websocket:
            event = json.loads(raw)
            events.append(event)
            if event.get("type") == "input_audio_buffer.append" and len(event.get("audio", "")) > 10000:
                await websocket.send(json.dumps({"type": "input_audio_buffer.speech_started", "item_id": "g2-item"}))
                await websocket.send(json.dumps({
                    "type": "conversation.item.input_audio_transcription.completed",
                    "item_id": "g2-item",
                    "transcript": "Trinity, hallo",
                }))
            elif event.get("type") == "response.create":
                await websocket.send(json.dumps({"type": "response.output_audio.delta", "delta": base64.b64encode(bytes(24_000 * 2 * 4)).decode()}))

    def run_server():
        asyncio.set_event_loop(server_loop)
        async def start_server():
            return await websockets.serve(upstream_handler, "127.0.0.1", upstream_port)

        server_holder["server"] = server_loop.run_until_complete(start_server())
        server_ready.set()
        server_loop.run_forever()
        server_holder["server"].close()
        server_loop.run_until_complete(server_holder["server"].wait_closed())
        server_loop.close()

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    assert server_ready.wait(3)
    router = MultiplexingVoiceRouter(
        "127.0.0.1", public_port, upstream_port, ["secret"], config_path, stt_port=stt_port
    )
    router.start()
    try:
        deadline = time.time() + 3
        while router._upstream is None and time.time() < deadline:
            time.sleep(0.02)
        assert router._upstream is not None
        with connect(f"ws://127.0.0.1:{public_port}/v1/realtime?device_id=companion:ipad&access_token=secret") as output:
            with connect(f"ws://127.0.0.1:{public_port}/v1/realtime?device_id=companion:iphone&access_token=secret") as microphone:
                assert json.loads(output.recv(timeout=2))["type"] == "session.created"
                assert json.loads(microphone.recv(timeout=2))["type"] == "session.created"
                output.send(json.dumps({"type": "input_audio_buffer.append", "audio": "ignored"}))
                microphone.send(json.dumps({"type": "input_audio_buffer.append", "audio": "microphone"}))
                output.send(json.dumps({"type": "response.create"}))
                assert json.loads(output.recv(timeout=2))["type"] == "response.output_audio.delta"
                next_config = json.loads(config_path.read_text())
                next_config["system"]["speech_output"]["device_id"] = "companion:second-ipad"
                config_path.write_text(json.dumps(next_config))
                with connect(f"ws://127.0.0.1:{public_port}/v1/realtime?device_id=companion:second-ipad&access_token=secret") as handoff:
                    assert json.loads(handoff.recv(timeout=2))["type"] == "session.created"
                    assert json.loads(handoff.recv(timeout=2))["type"] == "response.output_audio.delta"
                deadline = time.time() + 2
                while not any(event.get("audio") == "microphone" for event in events) and time.time() < deadline:
                    time.sleep(0.02)
                assert not any(event.get("audio") == "ignored" for event in events)
                assert any(event.get("audio") == "microphone" for event in events)

                selection = AudioInputSelection(config_path, router.selection.lease_path)
                selection.update({"action": "claim", "kind": "g2", "device_id": "g2:one"})
                body = json.dumps({"audio_base64": base64.b64encode(bytes(32_000)).decode()}).encode()
                request = Request(
                    f"http://127.0.0.1:{stt_port}/v1/audio/transcriptions",
                    data=body,
                    headers={"Authorization": "Bearer secret", "Content-Type": "application/json"},
                )
                with urlopen(request, timeout=5) as response:
                    assert json.load(response)["text"] == "Trinity, hallo"
                with connect(f"ws://127.0.0.1:{public_port}/v1/realtime?device_id=companion:second-ipad&access_token=secret") as chosen_output:
                    assert json.loads(chosen_output.recv(timeout=2))["type"] == "session.created"
                    with connect(f"ws://127.0.0.1:{public_port}/v1/realtime?device_id=g2:one&access_token=secret") as glasses:
                        assert json.loads(glasses.recv(timeout=2))["type"] == "session.created"
                        assert json.loads(glasses.recv(timeout=2))["type"] == "trinity.output_activity"
                        glasses.send(json.dumps({"type": "response.cancel"}))
                        received = []
                        deadline = time.time() + 2
                        while time.time() < deadline:
                            received.append(json.loads(chosen_output.recv(timeout=2))["type"])
                            if "input_audio_buffer.speech_started" in received:
                                break
                        assert "input_audio_buffer.speech_started" in received
                        deadline = time.time() + 2
                        while not any(event.get("type") == "response.cancel" for event in events) and time.time() < deadline:
                            time.sleep(0.02)
                        assert any(event.get("type") == "response.cancel" for event in events)
                assert any(
                    event.get("type") == "session.update"
                    and event["session"]["audio"]["input"]["turn_detection"]["create_response"] is False
                    for event in events
                )
                selection.update({"action": "release", "kind": "g2", "device_id": "g2:one"})
                assert selection.current()["device_id"] == "companion:iphone"
    finally:
        router.stop()
        server_loop.call_soon_threadsafe(server_loop.stop)
        server_thread.join(timeout=3)


def test_long_playback_tail_is_not_cut_off_at_30_seconds(tmp_path):
    config_path = tmp_path / "core" / "config.json"
    config_path.parent.mkdir()
    config_path.write_text(json.dumps({"system": {"audio_input": {"kind": "g2", "device_id": "g2:one"}}}))
    router = MultiplexingVoiceRouter("127.0.0.1", 1, 2, [], config_path)
    holds = []

    async def record(active, hold_ms):
        holds.append((active, hold_ms))

    router._notify_input_output_activity = record
    audio = base64.b64encode(bytes(24_000 * 2 * 40)).decode()

    class Stream:
        def __aiter__(self):
            self.events = iter((
                json.dumps({"type": "response.created"}),
                json.dumps({"type": "response.output_audio.delta", "delta": audio}),
                json.dumps({"type": "response.done"}),
            ))
            return self

        async def __anext__(self):
            try:
                return next(self.events)
            except StopIteration:
                raise StopAsyncIteration

    asyncio.run(router._reader(Stream()))
    assert holds[0] == (True, 0)
    assert holds[-1][0] is False
    assert holds[-1][1] > 30_000

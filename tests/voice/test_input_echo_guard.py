import base64
import json
import time

from voice.transport.multiplex_proxy import MultiplexingVoiceRouter


def router_for(tmp_path):
    return MultiplexingVoiceRouter("localhost", 1, 2, [], tmp_path / "core/config.json")


def test_server_masks_in_flight_echo_without_freezing_vad_time(tmp_path):
    router = router_for(tmp_path)
    packet = {"type": "input_audio_buffer.append", "audio": base64.b64encode(b"\x01\x02" * 1600).decode()}
    assert router._mask_input_echo(packet) == packet
    router._output_activity_started = True
    masked = router._mask_input_echo(packet)
    assert len(base64.b64decode(masked["audio"])) == 3200
    assert set(base64.b64decode(masked["audio"])) == {0}
    router._output_activity_started = False
    router._output_blocked_until = time.monotonic() + 1
    assert router._mask_input_echo(packet) != packet
    router._output_blocked_until = time.monotonic() - 1
    assert router._mask_input_echo(packet) == packet
    router._deck_active = True
    assert router._mask_input_echo(packet) != packet


def test_headphone_barge_in_and_explicit_cancel_stay_available(tmp_path):
    router = router_for(tmp_path)
    router._output_activity_started = True
    router._last_session_update = {"trinity_allow_barge_in": True}
    packet = {"type": "input_audio_buffer.append", "audio": "headphones"}
    assert router._mask_input_echo(packet) == packet
    assert router._mask_input_echo({"type": "response.cancel"}) == {"type": "response.cancel"}


def test_mask_rejects_malformed_or_unbounded_packets(tmp_path):
    router = router_for(tmp_path)
    router._output_activity_started = True
    assert router._mask_input_echo({"type": "input_audio_buffer.append", "audio": "@@"}) is None
    assert router._mask_input_echo({"type": "input_audio_buffer.append", "audio": "A" * 262148}) is None


def test_cancelled_audio_has_short_tail_and_cannot_replay(tmp_path):
    import asyncio
    router = router_for(tmp_path)
    notifications = []
    async def record(active, hold):
        notifications.append((active, hold))
    router._notify_input_output_activity = record
    class Stream:
        def __aiter__(self):
            self.events = iter([
                {"type": "response.created"},
                {"type": "response.output_audio.delta", "delta": base64.b64encode(bytes(48000 * 40)).decode()},
                {"type": "response.done", "response": {"status": "cancelled"}},
            ])
            return self
        async def __anext__(self):
            try:
                return json.dumps(next(self.events))
            except StopIteration:
                raise StopAsyncIteration
    asyncio.run(router._reader(Stream()))
    assert not router._response_chunks
    assert notifications[-1][0] is False
    assert 0 < notifications[-1][1] <= 350


def test_legacy_client_playback_gap_gets_only_silence_on_same_upstream(tmp_path):
    import asyncio
    router = router_for(tmp_path)
    sent = []
    router._upstream = object()
    router._input_id = lambda: "companion:ipad"
    router._output_activity_started = True
    router._last_audio_input_at = time.monotonic() - 1
    async def send(event):
        sent.append(event)
    router._send_upstream = send
    asyncio.run(router._keep_vad_clock_running())
    assert len(sent) == 1
    assert base64.b64decode(sent[0]["audio"]) == bytes(6400)
    asyncio.run(router._keep_vad_clock_running())
    assert len(sent) == 1, "Do not compete with an actively streaming microphone"

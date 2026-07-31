import base64
import json
import time

import numpy as np

from voice.config import default_voice_config, load_voice_config
from voice.local_realtime_client import LocalRealtimeAudioClient


def client(tmp_path):
    reference = tmp_path / "eve.mp3"
    reference.write_bytes(b"voice")
    raw = default_voice_config()
    raw.update({
        "engine": "eve",
        "profile": "eve-mac-local",
        "reference_audio": str(reference),
    })
    return LocalRealtimeAudioClient(load_voice_config(tmp_path, {"voice": raw}))


def test_session_enables_server_side_interruption(tmp_path):
    update = client(tmp_path)._session_update()

    turn_detection = update["session"]["audio"]["input"]["turn_detection"]
    assert turn_detection["interrupt_response"] is True
    assert turn_detection["create_response"] is True


def test_speech_started_flushes_buffered_audio(tmp_path):
    local = client(tmp_path)
    local._output.extend(b"audio")
    local._handle_event(json.dumps({"type": "input_audio_buffer.speech_started"}))

    assert local._output == bytearray()


def test_audio_delta_is_buffered_for_playback(tmp_path):
    local = client(tmp_path)
    audio = b"\x01\x00" * 32
    local._handle_event(json.dumps({
        "type": "response.output_audio.delta",
        "delta": base64.b64encode(audio).decode("ascii"),
    }))

    assert bytes(local._output) == audio


def test_obvious_playback_echo_is_not_forwarded(tmp_path):
    local = client(tmp_path)
    samples = np.full(512, 2_000, dtype=np.int16)
    local._played_output.append(samples.copy())
    local._last_output_at = time.monotonic()

    assert local._should_forward_microphone(samples.tobytes()) is False


def test_distinct_loud_speech_can_interrupt_playback(tmp_path):
    local = client(tmp_path)
    local._played_output.append(np.full(512, 2_000, dtype=np.int16))
    local._last_output_at = time.monotonic()
    speech = np.tile(np.array([1_400, -1_100, 800, -500], dtype=np.int16), 128)

    assert local._should_forward_microphone(speech.tobytes()) is True


def test_distinct_speech_cancels_current_response_before_forwarding(tmp_path):
    local = client(tmp_path)
    local._output.extend(b"buffered-audio")
    local._played_output.append(np.full(512, 2_000, dtype=np.int16))
    local._last_output_at = time.monotonic()
    speech = np.tile(np.array([1_400, -1_100, 800, -500], dtype=np.int16), 128)

    local._input_callback(speech.tobytes(), 512, None, None)

    assert local._output == bytearray()
    assert local._send_queue.get_nowait() == {"type": "response.cancel"}
    forwarded = local._send_queue.get_nowait()
    assert forwarded["type"] == "input_audio_buffer.append"


def test_output_callback_consumes_audio_without_microphone_coupling(tmp_path):
    local = client(tmp_path)
    samples = np.full(512, 1_250, dtype=np.int16)
    local._output.extend(samples.tobytes())
    output = bytearray(samples.nbytes)

    local._output_callback(output, 512, None, None)

    assert bytes(output) == samples.tobytes()
    assert local._output == bytearray()

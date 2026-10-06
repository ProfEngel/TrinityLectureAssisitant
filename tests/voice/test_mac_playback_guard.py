import base64
import json
from types import SimpleNamespace

import numpy as np

from core.voice import local_realtime_client as module
from core.voice.local_realtime_client import LocalRealtimeAudioClient, BLOCK_SAMPLES, OUTPUT_BLOCK_SAMPLES


def client(tmp_path, monkeypatch):
    monkeypatch.setattr(module.platform, "system", lambda: "Darwin")
    clock = [100.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    config = SimpleNamespace(home=tmp_path, profile=SimpleNamespace(internal_port=8766),
        barge_in_enabled=True, barge_in_min_level=420, echo_suppression_enabled=False)
    voice = LocalRealtimeAudioClient(config)
    voice._remote_speaker_url = "http://example.test/speaker"
    voice._remote_speaker_id = "desktop:test:mac"
    voice._desktop_output_enabled = voice._desktop_input_enabled = True
    return voice, clock


def audio(voice, blocks=1):
    pcm = np.full(OUTPUT_BLOCK_SAMPLES * blocks, 2000, dtype=np.int16).tobytes()
    voice._handle_event(json.dumps({"type": "response.output_audio.delta",
                                  "delta": base64.b64encode(pcm).decode()}))
    return pcm


def microphone(voice):
    voice._input_callback(np.full(BLOCK_SAMPLES, 15000, dtype=np.int16).tobytes(), BLOCK_SAMPLES, None, None)


def done(voice, status="completed"):
    voice._handle_event(json.dumps({"type": "response.done", "response": {"status": status}}))


def test_server_done_does_not_release_mic_while_audio_remains(tmp_path, monkeypatch):
    voice, clock = client(tmp_path, monkeypatch)
    pcm = audio(voice, 10)
    done(voice)
    clock[0] += 2
    for _ in range(20):
        microphone(voice)
    assert bytes(voice._output) == pcm
    assert voice._send_queue.empty()  # No audio echo or response.cancel.


def test_pcm_drain_hardware_delay_and_echo_tail_then_mic_resumes(tmp_path, monkeypatch):
    voice, clock = client(tmp_path, monkeypatch)
    pcm = audio(voice)
    done(voice)
    out = bytearray(len(pcm))
    voice._output_callback(out, OUTPUT_BLOCK_SAMPLES,
        SimpleNamespace(currentTime=8000.0, outputBufferDacTime=8000.1), None)
    assert out == pcm and not voice._output
    clock[0] += 0.45
    microphone(voice)
    assert voice._send_queue.empty()
    clock[0] += 0.04
    microphone(voice)
    assert voice._send_queue.get_nowait()["type"] == "input_audio_buffer.append"
    voice._flush_audio_debug()


def test_sentence_gap_stays_guarded_but_stalled_stream_is_bounded(tmp_path, monkeypatch):
    voice, clock = client(tmp_path, monkeypatch)
    audio(voice)
    voice._output_callback(bytearray(OUTPUT_BLOCK_SAMPLES * 2), OUTPUT_BLOCK_SAMPLES, None, None)
    clock[0] += 1
    microphone(voice)
    assert voice._send_queue.empty()
    clock[0] += module.STREAM_GAP_LIMIT
    microphone(voice)
    assert voice._send_queue.get_nowait()["type"] == "input_audio_buffer.append"


def test_explicit_headphone_mode_keeps_voice_interruption(tmp_path, monkeypatch):
    voice, _ = client(tmp_path, monkeypatch)
    voice._headphone_barge_in = True
    audio(voice, 10)
    for _ in range(module.BARGE_IN_CONFIRM_BLOCKS):
        microphone(voice)
    assert not voice._output
    assert voice._send_queue.get_nowait()["type"] == "response.cancel"


def test_g2_stop_still_flushes_mac_even_with_guard_active(tmp_path, monkeypatch):
    voice, _ = client(tmp_path, monkeypatch)
    audio(voice, 10)
    voice._handle_event(json.dumps({"type": "input_audio_buffer.speech_started"}))
    assert not voice._output
    assert voice._streaming_until == 0


def test_output_handoff_drops_mac_audio_without_cancelling_ipad(tmp_path, monkeypatch):
    voice, _ = client(tmp_path, monkeypatch)
    audio(voice, 10)
    voice._desktop_output_enabled = False
    out = bytearray(OUTPUT_BLOCK_SAMPLES * 2)
    voice._output_callback(out, OUTPUT_BLOCK_SAMPLES, None, None)
    assert out == bytes(len(out)) and not voice._output
    assert voice._send_queue.empty()
    audio(voice)
    assert not voice._output


def test_mac_input_respects_other_speakers_activity_only_locally(tmp_path, monkeypatch):
    voice, clock = client(tmp_path, monkeypatch)
    voice._desktop_output_enabled = False
    voice._handle_event(json.dumps({"type": "trinity.output_activity", "active": True}))
    microphone(voice)
    assert voice._send_queue.empty()
    voice._handle_event(json.dumps({"type": "trinity.output_activity", "active": False, "hold_ms": 800}))
    clock[0] += 0.81
    microphone(voice)
    assert voice._send_queue.get_nowait()["type"] == "input_audio_buffer.append"


def test_non_mac_client_has_no_new_guard(tmp_path, monkeypatch):
    monkeypatch.setattr(module.platform, "system", lambda: "Linux")
    voice = LocalRealtimeAudioClient(SimpleNamespace(home=tmp_path, profile=SimpleNamespace(internal_port=8766)))
    voice._output.extend(b"\x01\x00" * 10000)
    assert not voice._microphone_playback_guard_active()


def test_stop_queue_is_owner_checked_at_execution_time(tmp_path, monkeypatch):
    voice, _ = client(tmp_path, monkeypatch)
    voice._speech_queue_path.parent.mkdir(parents=True)
    command = {"action": "stop", "device_id": voice._remote_speaker_id}
    voice._speech_queue_path.write_text(json.dumps(command) + "\n")
    audio(voice, 10)
    voice._desktop_output_enabled = False  # Handoff after menu click.
    voice._consume_speech_queue()
    assert voice._send_queue.empty()
    voice._speech_queue_offset = 0
    voice._desktop_output_enabled = True
    voice._consume_speech_queue()
    assert voice._send_queue.get_nowait()["type"] == "response.cancel"
    assert not voice._output


def test_cancelled_response_releases_remote_echo_guard(tmp_path, monkeypatch):
    voice, _ = client(tmp_path, monkeypatch)
    voice._desktop_output_enabled = False
    voice._handle_event(json.dumps({"type": "trinity.output_activity", "active": True}))
    assert voice._microphone_playback_guard_active()
    done(voice, "cancelled")
    assert not voice._microphone_playback_guard_active()

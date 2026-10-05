from types import SimpleNamespace

import numpy as np

from voice.local_realtime_client import (
    BLOCK_SAMPLES, OUTPUT_BLOCK_SAMPLES, VIRTUAL_BLOCK_SAMPLES,
    LocalRealtimeAudioClient,
)


def client(tmp_path):
    return LocalRealtimeAudioClient(SimpleNamespace(home=tmp_path, profile=SimpleNamespace(internal_port=8766)))


def test_system_audio_downmixes_to_single_shared_stt_input(tmp_path):
    voice = client(tmp_path)
    voice._desktop_input_enabled = True
    voice._system_audio_enabled = True
    stereo = np.full((VIRTUAL_BLOCK_SAMPLES, 2), 1000, dtype=np.int16).tobytes()
    voice._system_audio_callback(stereo, VIRTUAL_BLOCK_SAMPLES, None, None)
    voice._input_callback(bytes(BLOCK_SAMPLES * 2), BLOCK_SAMPLES, None, None)
    import base64
    event = voice._send_queue.get_nowait()
    pcm = np.frombuffer(base64.b64decode(event["audio"]), dtype=np.int16)
    assert pcm.size == BLOCK_SAMPLES
    assert np.all(pcm == 1000)


def test_blackhole_virtual_mic_contains_user_and_eve_audio(tmp_path):
    voice = client(tmp_path)
    voice._desktop_input_enabled = False
    voice._desktop_output_enabled = True
    voice._broadcast_enabled = True
    microphone = np.full(BLOCK_SAMPLES, 1000, dtype=np.int16).tobytes()
    eve = np.full(OUTPUT_BLOCK_SAMPLES, 2000, dtype=np.int16).tobytes()
    voice._input_callback(microphone, BLOCK_SAMPLES, None, None)
    voice._output.extend(eve)
    voice._output_callback(bytearray(len(eve)), OUTPUT_BLOCK_SAMPLES, None, None)
    rendered = bytearray(VIRTUAL_BLOCK_SAMPLES * 2 * 2)
    voice._virtual_output_callback(rendered, VIRTUAL_BLOCK_SAMPLES, None, None)
    stereo = np.frombuffer(rendered, dtype=np.int16).reshape(-1, 2)
    assert np.all(stereo[:, 0] == 3000)
    assert np.array_equal(stereo[:, 0], stereo[:, 1])

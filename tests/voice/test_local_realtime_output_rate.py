from types import SimpleNamespace

import numpy as np

from voice.local_realtime_client import (
    BLOCK_SAMPLES, OUTPUT_BLOCK_SAMPLES, OUTPUT_SAMPLE_RATE, SAMPLE_RATE,
    LocalRealtimeAudioClient,
)


def test_mac_plays_eve_pcm_at_its_24khz_rate_and_keeps_16khz_microphone(tmp_path):
    client = LocalRealtimeAudioClient(SimpleNamespace(home=tmp_path, profile=SimpleNamespace(internal_port=8766)))
    assert SAMPLE_RATE == 16_000
    assert OUTPUT_SAMPLE_RATE == 24_000
    assert OUTPUT_BLOCK_SAMPLES / OUTPUT_SAMPLE_RATE == BLOCK_SAMPLES / SAMPLE_RATE
    client._desktop_output_enabled = True
    tone = (np.sin(np.arange(OUTPUT_BLOCK_SAMPLES) * 0.04) * 10000).astype(np.int16).tobytes()
    client._output.extend(tone)
    out = bytearray(len(tone))
    client._output_callback(out, OUTPUT_BLOCK_SAMPLES, None, None)
    assert bytes(out) == tone
    assert client._played_output[-1].size == BLOCK_SAMPLES

"""Exercise the real Eve pipeline without playing test audio on user devices."""
import base64
import json
import sys
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.remote_client import RemoteTrinityClient
from core.voice.config import load_voice_config
from core.voice.device_identity import desktop_device_id
from core.voice.local_realtime_client import LocalRealtimeAudioClient
from websockets.sync.client import connect

home = Path(__file__).resolve().parents[1]
config = json.loads((home / "core/config.json").read_text())
remote = RemoteTrinityClient(config["client"]["server_url"], token=config["client"]["token"],
                             profile=config["system"]["profile"], timeout=10)
mac_id = desktop_device_id(home, config["system"]["profile"])
probe_id = "desktop:diagnostic:voice-stability"
voice = load_voice_config(home, config)
client = LocalRealtimeAudioClient(voice, endpoint=voice.remote_voice_url,
                                  access_token=voice.remote_voice_token or voice.access_token)
uri = urlsplit(client._connection_uri())
query = dict(parse_qsl(uri.query))
query["device_id"] = probe_id
endpoint = urlunsplit((uri.scheme, uri.netloc, uri.path, urlencode(query), uri.fragment))
results = []
previous_input = remote.get_audio_input()
previous_output = remote.get_speaker()
try:
    remote.set_speaker(probe_id, "Silent voice diagnostic")
    with connect(endpoint, open_timeout=8, max_size=None) as ws:
        ws.recv(timeout=5)
        for text in ("Ja, ich höre dich laut und deutlich. Wie kann ich dir helfen?",
                     "Hallo, ich bin bereit.",
                     "Eine Tabelle lässt sich am besten erklären, indem wir zuerst die Spalten benennen und anschließend ein konkretes Beispiel gemeinsam durchgehen."):
            start = time.monotonic()
            ws.send(json.dumps({"type": "response.create", "response": {
                "conversation": "none", "input": [{"type": "message", "role": "user",
                "content": [{"type": "input_text", "text": "[[TRINITY_READ_ALOUD_V1]]\n" + text}]}],
                "output_modalities": ["audio"], "max_output_tokens": 4096}}))
            first = None
            size = 0
            audio = bytearray()
            while True:
                event = json.loads(ws.recv(timeout=40))
                if event["type"] in {"response.audio.delta", "response.output_audio.delta"}:
                    first = first or time.monotonic()
                    block = base64.b64decode(event["delta"])
                    size += len(block)
                    audio.extend(block)
                if event["type"] == "error":
                    raise RuntimeError(event.get("error", {}).get("message", "Realtime error"))
                if event["type"] == "response.done":
                    break
            if not size:
                raise RuntimeError("No validated Eve audio produced for the test utterance")
            results.append({"words": len(text.split()), "first_audio_seconds": round(first - start, 2) if first else None,
                            "audio_seconds": round(size / 48000, 2),
                            "completed_seconds": round(time.monotonic() - start, 2)})
            # Save PCM only for an optional inspection; no automatic playback.
            import wave
            out = home / "TrinityRuntime/voice" / f"stability-probe-{len(results)}.wav"
            with wave.open(str(out), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(24000)
                wav.writeframes(audio)
            time.sleep(0.3)
        # Feed one saved utterance back through the SAME selected Parakeet.
        remote.set_audio_input(probe_id, "Silent microphone diagnostic")
        ws.send(json.dumps({"type": "session.update", "session": {
            "type": "realtime", "audio": {"input": {
                "transcription": {"model": "parakeet-tdt", "language": "de"},
                "turn_detection": {"type": "server_vad", "create_response": False,
                                   "silence_duration_ms": 420}}}}}))
        while True:
            event = json.loads(ws.recv(timeout=5))
            if event["type"] == "error":
                raise RuntimeError(event.get("error", {}).get("message"))
            if event["type"] == "session.updated":
                break
        import numpy as np
        with wave.open(str(home / "TrinityRuntime/voice/stability-probe-3.wav")) as wav:
            pcm = np.frombuffer(wav.readframes(wav.getnframes()), dtype=np.int16)
        resampled = np.interp(np.arange(0, pcm.size, 1.5), np.arange(pcm.size), pcm).astype(np.int16)
        resampled = np.concatenate([resampled, np.zeros(16000, dtype=np.int16)])
        start = time.monotonic()
        ws.send(json.dumps({"type": "input_audio_buffer.append", "audio": base64.b64encode(resampled.tobytes()).decode()}))
        while True:
            event = json.loads(ws.recv(timeout=20))
            if event["type"] == "conversation.item.input_audio_transcription.completed":
                print("Parakeet roundtrip:", event.get("transcript"), flush=True)
                print("STT processing seconds:", round(time.monotonic() - start, 2), flush=True)
                break
        start = time.monotonic()
        ws.send(json.dumps({"type": "response.create", "response": {
            "conversation": "none", "input": [{"type": "message", "role": "user",
            "content": [{"type": "input_text", "text": "Trinity, antworte bitte mit einem kurzen Satz: Was bedeutet Latenz?"}]}],
            "output_modalities": ["audio"]}}))
        first = None
        size = 0
        while True:
            event = json.loads(ws.recv(timeout=40))
            if event["type"] == "response.output_audio.delta":
                first = first or time.monotonic()
                size += len(base64.b64decode(event["delta"]))
            if event["type"] == "response.done":
                break
        print("LLM + TTS first audio seconds:", round(first - start, 2) if first else None, flush=True)
        print("LLM + TTS audio seconds:", round(size / 48000, 2), flush=True)
finally:
    # Restore the actual previous device, not unconditionally the Mac. Never
    # override a user who selected a different device while the probe ran.
    if remote.get_audio_input().get('device_id') == probe_id:
        remote.set_audio_input(previous_input['device_id'], previous_input.get('label', ''),
                               kind=previous_input.get('kind', 'desktop'))
    if remote.get_speaker().get('device_id') == probe_id:
        remote.set_speaker(previous_output['device_id'], previous_output.get('label', ''),
                           kind=previous_output.get('kind', 'desktop'))
print(json.dumps(results, ensure_ascii=False, indent=2))

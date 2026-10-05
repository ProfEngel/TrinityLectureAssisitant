"""Test voice + desktop vision with a synthetic image, never private contents."""
import base64
import io
import json
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from PIL import Image, ImageDraw, ImageFont
from websockets.sync.client import connect

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.remote_client import RemoteTrinityClient
from core.voice.config import load_voice_config
from core.voice.device_identity import desktop_device_id
from core.voice.local_realtime_client import LocalRealtimeAudioClient

home = Path(__file__).resolve().parents[1]
config = json.loads((home / "core/config.json").read_text())
remote = RemoteTrinityClient(config["client"]["server_url"], token=config["client"]["token"],
                             profile=config["system"]["profile"], timeout=10)
device = desktop_device_id(home, config["system"]["profile"])
probe = "desktop:diagnostic:window-voice"
client_id = "diagnostic:" + uuid.uuid4().hex
image = Image.new("RGB", (1600, 1000), "white")
draw = ImageDraw.Draw(image)
font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 64)
draw.text((100, 100), "Fenstertest: TRINITY", font=font, fill="black")
draw.text((100, 250), "Wert: 42", font=font, fill="black")
buffer = io.BytesIO()
image.save(buffer, "JPEG", quality=78)
voice = load_voice_config(home, config)
audio_client = LocalRealtimeAudioClient(voice, endpoint=voice.remote_voice_url,
                                       access_token=voice.remote_voice_token or voice.access_token)
uri = urlsplit(audio_client._connection_uri())
query = dict(parse_qsl(uri.query))
query["device_id"] = probe
endpoint = urlunsplit((uri.scheme, uri.netloc, uri.path, urlencode(query), uri.fragment))
try:
    remote.set_speaker(probe, "Silent window diagnostic")
    remote.set_desktop_context({"client_id": client_id, "device_id": device, "sequence": 1,
                                "active": True, "title": "Synthetischer Fenstertest",
                                "image_base64": base64.b64encode(buffer.getvalue()).decode()})
    with connect(endpoint, open_timeout=8, max_size=None) as ws:
        ws.recv(timeout=5)
        started = time.monotonic()
        ws.send(json.dumps({"type": "response.create", "response": {"conversation": "none",
            "input": [{"type": "message", "role": "user", "content": [{"type": "input_text",
                "text": "Trinity, lies bitte den Namen und den Zahlenwert in diesem freigegebenen Fenster. Antworte mit einem Satz."}]}],
            "output_modalities": ["audio"]}}))
        text = []
        first = None
        size = 0
        while True:
            event = json.loads(ws.recv(timeout=40))
            kind = event["type"]
            if kind in {"response.output_audio_transcript.done", "response.output_text.done"}:
                text.append(event.get("transcript") or event.get("text") or "")
            if kind == "response.output_audio.delta":
                first = first or time.monotonic()
                size += len(base64.b64decode(event["delta"]))
            if kind == "error":
                raise RuntimeError(event.get("error", {}).get("message"))
            if kind == "response.done":
                break
        print(json.dumps({"answer": " ".join(dict.fromkeys(text)),
                          "first_audio_seconds": round(first - started, 2) if first else None,
                          "audio_seconds": round(size / 48000, 2)}, ensure_ascii=False))
        if not first or "42" not in " ".join(text):
            raise RuntimeError("Window vision/voice test did not pass")
finally:
    remote.set_desktop_context({"client_id": client_id, "device_id": device,
                                "sequence": 2, "active": False})
    remote.set_speaker(device, "Trinity Mac")

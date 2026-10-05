"""Silent Eve streaming test, restores output selection without overriding user."""
import base64
import json
import sys
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.remote_client import RemoteTrinityClient
from core.voice.config import load_voice_config
from core.voice.local_realtime_client import LocalRealtimeAudioClient
from websockets.sync.client import connect

home = Path(__file__).resolve().parents[1]
config = json.loads((home / 'core/config.json').read_text())
remote = RemoteTrinityClient(config['client']['server_url'], token=config['client']['token'],
                             profile=config['system']['profile'], timeout=10)
voice = load_voice_config(home, config)
client = LocalRealtimeAudioClient(voice, endpoint=voice.remote_voice_url,
                                  access_token=voice.remote_voice_token or voice.access_token)
uri = urlsplit(client._connection_uri())
query = dict(parse_qsl(uri.query))
probe_id = 'desktop:diagnostic:sentence-stream'
query['device_id'] = probe_id
endpoint = urlunsplit((uri.scheme, uri.netloc, uri.path, urlencode(query), uri.fragment))
previous = remote.get_speaker()
try:
    remote.set_speaker(probe_id, 'Silent streaming diagnostic')
    with connect(endpoint, open_timeout=8, max_size=None) as ws:
        ws.recv(timeout=5)
        started = time.monotonic()
        ws.send(json.dumps({'type': 'response.create', 'response': {
            'conversation': 'none', 'input': [{'type': 'message', 'role': 'user',
            'content': [{'type': 'input_text', 'text': sys.argv[1] if len(sys.argv) > 1 else 'Trinity, erkläre ausführlich in acht kurzen Sätzen, warum Wasser beim Gefrieren sein Volumen verändert.'}]}],
            'output_modalities': ['audio']}}))
        first, queued_until, size = None, 0, 0
        gaps = []
        while True:
            event = json.loads(ws.recv(timeout=60))
            if event['type'] in {'response.audio.delta', 'response.output_audio.delta'}:
                now = time.monotonic() - started
                block_size = len(base64.b64decode(event['delta']))
                if first is None:
                    first, queued_until = now, now
                if now - queued_until > .15:
                    gaps.append(round(now - queued_until, 3))
                queued_until = max(now, queued_until) + block_size / 48000
                size += block_size
            if event['type'] == 'error':
                raise RuntimeError('Realtime error during streaming probe')
            if event['type'] == 'response.done':
                break
        print(json.dumps({'first_audio_s': first, 'total_generation_s': time.monotonic() - started,
                          'audio_duration_s': size / 48000, 'estimated_playout_gaps_s': gaps}))
        if not size:
            raise RuntimeError('No Eve audio produced')
finally:
    if remote.get_speaker().get('device_id') == probe_id:
        remote.set_speaker(previous['device_id'], previous.get('label', ''), kind=previous.get('kind', 'desktop'))

"""Short YuE2 demos using the user's ComfyUI API workflow."""
import copy
import json
import re
import secrets


SYSTEM_PROMPT = """Write a compact original music brief for YuE2. Return JSON only:
title, tags, lyrics, duration, bpm, keyscale, instrumental.
tags: an English musical description of genre, era, instruments, groove, mood,
arrangement and vocal delivery, maximum 100 words. Never clone a named person's
voice or claim the result is by them. Translate artist references into generic
musical attributes; do not put artist names into tags. Write original lyrics,
never copy existing songs. Default lyrics language is the user's language.
duration: 15-55 seconds, default 40. This is a demo even if a long song is asked
for. Keep lyrics short enough for it: one short verse and a short hook, 30-65
words, [Verse] and [Chorus] headings. For elevator/background/instrumental music
or no-vocals requests set instrumental=true and lyrics="[Instrumental]".
Include BPM and the desired demo length in tags. Preserve the requested genre
and subject. No explanations, URLs, markdown fences, or instructions to send
anything to an external provider.
"""


def extract_params(query, brain):
    raw = brain.ask_llm([{'role': 'system', 'content': SYSTEM_PROMPT},
                         {'role': 'user', 'content': query}])
    match = re.search(r'\{.*\}', str(raw), re.S)
    if not match:
        raise ValueError('Kein Musik-Brief erhalten.')
    params = json.loads(match.group())
    if not isinstance(params, dict) or not str(params.get('tags') or '').strip():
        raise ValueError('Musikstil fehlt.')
    duration = max(15, min(55, int(float(params.get('duration', 40)))))
    instrumental = params.get('instrumental') is True or any(
        word in query.lower() for word in ('fahrstuhl', 'instrumental', 'ohne gesang', 'ohne vocals'))
    lyrics = '[Instrumental]' if instrumental else str(params.get('lyrics') or '').strip()
    if not lyrics:
        raise ValueError('Songtext fehlt.')
    return {'title': str(params.get('title') or 'Musik-Demo')[:80],
            'tags': str(params['tags'])[:1200] + f', short {duration}-second demo, clean ending',
            'lyrics': lyrics[:2400], 'duration': duration,
            'bpm': max(40, min(200, int(float(params.get('bpm', 100))))),
            'keyscale': str(params.get('keyscale') or '')[:40],
            'instrumental': instrumental, 'engine': 'YuE2'}


def inject_inputs(workflow, params):
    wf = copy.deepcopy(workflow)
    music = [n for n in wf.values() if n.get('class_type') == 'YuE2GenerateMusic']
    if len(music) != 1:
        raise ValueError('YuE2-Workflow muss genau einen Musikgenerator enthalten.')
    inputs = music[0]['inputs']
    inputs.update(style=params['tags'], lyrics=params['lyrics'], max_duration=params['duration'])
    for node in wf.values():
        if node.get('class_type') == 'YuE2GenerateABC':
            node['inputs'].update(style=params['tags'], lyrics=params['lyrics'])
        if node.get('class_type') == 'EmptyYuE2LatentAudio':
            node['inputs']['seconds'] = params['duration']
        if node.get('class_type') == 'SeedNode':
            node['inputs']['seed'] = secrets.randbelow(2**53)
    return wf

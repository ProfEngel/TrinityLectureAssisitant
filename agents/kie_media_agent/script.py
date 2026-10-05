"""Shared kie.ai raster-image and Suno music generation; keys stay server-side."""
import html
import json
import os
import re
import secrets
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from image_routing import is_image_request
from media_policy import wants_song
from agents.comfyui_agent.script import _build_audio_payload

API = "https://api.kie.ai/api/v1"
IMAGE_MODEL = "gpt-image-2-5-flare-text-to-image"
MUSIC_MODEL = "ai-music-api/generate"
PRIORITY = 110

IMAGE_BRIEF = """Create one polished image-generation brief. Preserve the user's
facts and requested image/diagram type. Prefer muted pastel colors, clear visual
hierarchy and generous whitespace. All visible text, titles and labels MUST be
German, including precise umlauts. Use short, explicitly quoted German labels.
No Mermaid, code, markdown, invented data or fabricated numerical values.
For a metaphor image avoid unnecessary text. Landscape composition 16:9, 2K.
Return only the finished prompt, maximum 1800 characters."""
MUSIC_BRIEF = """Write an ORIGINAL short song brief for Suno V6. JSON only:
title, style, lyrics, instrumental, duration. Style in English, max 800 chars;
lyrics in user's language, default German, one short verse and chorus.
Use generic musical traits for artist references, never copy existing lyrics
or clone a named artist's voice. Instrumental/elevator music: instrumental=true,
lyrics="". Duration 15-55 seconds, default 40, clean ending. No extra prose."""


def can_handle_song(query):
    return wants_song(query)


class KieJobUncertain(RuntimeError):
    """A submitted job may still finish; never start a fallback job."""


def can_handle(query):
    return is_image_request(query) or can_handle_song(query)


def image_task(prompt):
    return {"model": IMAGE_MODEL, "input": {
        "prompt": prompt + "\nAlle sichtbaren Texte ausschließlich auf Deutsch. Querformat 16:9, 2K.",
        "aspect_ratio": "16:9", "resolution": "2K"}}


def music_task(brief):
    instrumental = brief.get("instrumental") is True
    style = str(brief.get("style") or "").strip()[:1000]
    lyrics = str(brief.get("lyrics") or "").strip()[:5000]
    if not style or (not instrumental and not lyrics):
        raise ValueError("Musikstil oder Songtext fehlt; kein Auftrag gesendet.")
    return {"model": MUSIC_MODEL, "input": {
        "model": "V6", "custom_mode": True, "instrumental": instrumental,
        "style": style, "title": str(brief.get("title") or "Trinity Musik")[:80],
        "lyrics": "" if instrumental else lyrics,
        "prompt": style if instrumental else lyrics,
        "duration": max(15, min(55, int(float(brief.get("duration", 40)))))}}


def _key(brain):
    # Reuse the protected Workbench secret store, never add keys to prompts.
    home = Path(brain.config_path).resolve().parent.parent
    from workbench import WorkbenchManager
    return str(WorkbenchManager(home)._load_secrets(getattr(brain, "config", {})).get("kie_ai") or "").strip()


def submit_and_wait(task, key, timeout=900):
    headers = {"Authorization": f"Bearer {key}"}
    response = requests.post(API + "/jobs/createTask", headers=headers, json=task, timeout=40)
    response.raise_for_status()
    body = response.json()
    if body.get("code") != 200 or not (body.get("data") or {}).get("taskId"):
        raise RuntimeError(f"kie.ai lehnt den Auftrag ab (Code {body.get('code')}). Kein Ersatzanbieter verwendet.")
    task_id = body["data"]["taskId"]
    print(f"kie.ai Medienauftrag angenommen: {task_id}", flush=True)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            response = requests.get(API + "/jobs/recordInfo", headers=headers, params={"taskId": task_id}, timeout=30)
            response.raise_for_status()
            body = response.json()
        except (requests.RequestException, ValueError):
            raise KieJobUncertain(f"kie.ai Auftrag {task_id} wurde angenommen; Status unklar. Kein zweiter Auftrag gestartet.")
        if body.get("code") != 200:
            raise KieJobUncertain(f"kie.ai Statusabfrage fehlgeschlagen (Code {body.get('code')}); Auftrag {task_id} nicht erneut gesendet.")
        data = body.get("data") or {}
        state = str(data.get("state") or "").lower()
        if state in ("fail", "failed"):
            raise RuntimeError(f"kie.ai Generierung fehlgeschlagen (Code {data.get('failCode')}); kein Ersatzanbieter verwendet.")
        if state == "success":
            result = data.get("resultJson") or {}
            if isinstance(result, str):
                result = json.loads(result)
            urls = _result_urls(result) or _result_urls(data)
            if not urls:
                print("kie.ai Ergebnisfelder:", sorted(data), "Resultfelder:", sorted(result) if isinstance(result, dict) else type(result).__name__, flush=True)
                raise KieJobUncertain(f"kie.ai Auftrag {task_id} meldet fertig, liefert aber keine erkannte Mediendatei. Kein zweiter Auftrag gestartet.")
            return task_id, urls
        time.sleep(3)
    raise KieJobUncertain(f"kie.ai Auftrag {task_id} läuft länger als erwartet; nicht erneut gesendet. Bitte kie.ai-Auftragsstatus prüfen.")


def _result_urls(result):
    urls = []
    if isinstance(result, list):
        for item in result:
            if isinstance(item, str) and item.startswith('https://'):
                urls.append(item)
            elif isinstance(item, (dict, list)):
                urls.extend(_result_urls(item))
    elif isinstance(result, dict):
        for key, value in result.items():
            if key.replace('_', '').lower() in ('resulturls', 'audiourls', 'audiourl', 'sourceaudiourl', 'imageurl'):
                urls.extend([value] if isinstance(value, str) and value.startswith('https://') else _result_urls(value))
            elif isinstance(value, (dict, list)):
                urls.extend(_result_urls(value))
    return list(dict.fromkeys(urls))


def _download(url, target):
    parsed = urlparse(str(url))
    if parsed.scheme != "https" or not parsed.hostname or parsed.username:
        raise ValueError("Ungültige kie.ai-Medienadresse.")
    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with target.open("xb") as handle:
                total = 0
                for chunk in response.iter_content(65536):
                    total += len(chunk)
                    if total > 100 * 1024 * 1024:
                        raise ValueError("Mediendatei zu groß.")
                    handle.write(chunk)
            if total == 0:
                raise ValueError("Leere Mediendatei.")
        except Exception:
            target.unlink(missing_ok=True)
            raise
    return str(target)


def _execute(query, context, music=False):
    brain = (context or {}).get("brain")
    if brain is None:
        return {"has_payload": False, "search_context": "Trinity-Medienkontext fehlt."}
    try:
        key = _key(brain)
        if not key:
            raise ValueError("kie.ai-Schlüssel fehlt in der geschützten Serverkonfiguration.")
        raw = brain.ask_llm([{"role": "system", "content": MUSIC_BRIEF if music else IMAGE_BRIEF},
                             {"role": "user", "content": query}])
        if not raw:
            raise ValueError("Medien-Brief konnte nicht erstellt werden; kein Auftrag gesendet.")
        if music:
            match = re.search(r"\{.*\}", str(raw), re.S)
            if not match:
                raise ValueError("Ungültiger Musik-Brief; kein Auftrag gesendet.")
            brief = json.loads(match.group())
            if any(w in query.lower() for w in ("fahrstuhl", "instrumental", "ohne gesang")):
                brief["instrumental"] = True
            task = music_task(brief)
        else:
            task = image_task(str(raw)[:1800])
        task_id, urls = submit_and_wait(task, key)
        home = Path(brain.config_path).resolve().parent.parent
        suffix = secrets.token_hex(8)
        if music:
            audio_urls = [u for u in urls if urlparse(u).path.lower().endswith((".mp3", ".wav", ".m4a"))]
            target = home / "agents/comfyui_agent/media/output/audio" / f"kie_suno_{suffix}.mp3"
            path = _download((audio_urls or urls)[0], target)
            payload = _build_audio_payload(path, task["input"]["title"], {
                "engine": "kie.ai · Suno V6", "tags": task["input"]["style"], "lyrics": task["input"]["lyrics"], "duration": task["input"]["duration"]})
            payload = payload.replace('<audio controls', '<audio src="' + html.escape(target.resolve().as_uri(), quote=True) + '" controls')
        else:
            target = home / "gen_images" / f"kie_flare_{suffix}.png"
            path = _download(urls[0], target)
            payload = '<!-- KEEP_OPEN --><!-- IMAGE_PAYLOAD --><h2>kie.ai · GPT Image 2.5 Flare</h2><img style="width:100%;border-radius:10px" src="' + html.escape(target.resolve().as_uri(), quote=True) + '">'
        brain.last_media_path = path
        return {"has_payload": True, "html_payload": payload,
                "direct_answer": "Das Lied ist fertig und im Medien-Player verfügbar." if music else "Das generierte Bild ist fertig und im Medien-Player verfügbar.",
                "search_context": "", "task_id": task_id}
    except Exception as exc:
        message = str(exc).replace(key, "[geschützt]") if 'key' in locals() and key else str(exc)
        return {"has_payload": False, "html_payload": "", "search_context": message[:500],
                "fallback_safe": 'task_id' not in locals() and not isinstance(exc, KieJobUncertain) and (
                    not isinstance(exc, requests.RequestException) or isinstance(exc, requests.ConnectTimeout) or
                    getattr(getattr(exc, 'response', None), 'status_code', None) in (401, 403, 404, 422, 429)),
                "direct_answer": ("Es wurde kein Lied bereitgestellt. " if music else "Es wurde kein Bild bereitgestellt. ") + message[:500]}


def execute(query, context=None):
    return _execute(query, context, music=can_handle_song(query))


def execute_t2a(query, context=None):
    return _execute(query, context, music=True)

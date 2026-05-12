import os
import json
import time
import copy
import requests
from typing import Optional


# Ordner-Pfade relativ zu diesem Script
AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKFLOWS_DIR = os.path.join(AGENT_DIR, "workflows")
MEDIA_INPUT_DIR = os.path.join(AGENT_DIR, "media", "input")
MEDIA_OUTPUT_DIR = os.path.join(AGENT_DIR, "media", "output")

# Trigger-Keywords: Explizit auf ComfyUI / lokale Generierung zeigen
TRIGGER_WORDS = [
    "lokales bild", "lokal generier", "lokal erstell",
    "auf meinem server", "auf dem server", "flux render",
    "comfyui", "flux bild", "flux erstell", "flux generier",
    "render ein", "rendere", "flux2", "sierra", "snofs", "sns1.2"
]

# Song-Trigger-Keywords
SONG_TRIGGER_WORDS = [
    "song", "lied", "musik", "audio", "komponier", "acestep", "bpm", "lyrics"
]

# Video-Trigger-Keywords (für Telegram-Foto-Caption)
VIDEO_TRIGGER_WORDS = [
    "video", "kurzvideo", "animier", "animation", "in bewegung",
    "bewegen", "lebendig", "zum video", "als video", "ltx", "i2v",
    "film", "clip", "bewegtbild"
]

# Workflow-Mapping
WORKFLOW_T2I = "Flux2_Klein_T2I_API.json"
WORKFLOW_I2I = "Flux2_klein_I2I_API.json"
WORKFLOW_T2A = "AceStep1.5_T2A_API.json"
WORKFLOW_I2V = "LTX2.3_I2V_API.json"

# Node-IDs pro Workflow
T2I_PROMPT_NODE = "14"   # CLIPTextEncode Positive Prompt
T2I_WIDTH_NODE  = "9"    # PrimitiveInt "Width"
T2I_HEIGHT_NODE = "10"   # PrimitiveInt "Height"

I2I_PROMPT_NODE = "6"    # CLIPTextEncode Positive Prompt
I2I_IMAGE_NODE  = "46"   # LoadImage
I2I_MEGAPIXEL_NODE = "45" # ImageScaleToTotalPixels
I2I_LATENT_NODE = "47"   # EmptyFlux2LatentImage (Dimensionen)
I2I_SCHEDULER_NODE = "48" # Flux2Scheduler (Dimensionen)

T2A_ENCODE_NODE = "94"   # TextEncodeAceStepAudio1.5
T2A_LATENT_NODE = "98"   # EmptyAceStep1.5LatentAudio

I2V_IMAGE_NODE  = "45"   # LoadImage "First Frame"
I2V_WIDTH_NODE  = "66"   # INTConstant "Width"
I2V_HEIGHT_NODE = "67"   # INTConstant "Height"
I2V_LENGTH_NODE = "68"   # INTConstant "Length (in seconds)"
I2V_PROMPT_NODE = "173"  # PrimitiveStringMultiline "Positive Prompt"

# PowerLoraLoader-Node IDs
LORA_NODE_T2I = "19"   # Power Lora Loader im T2I-Workflow
LORA_NODE_I2I = "74"   # Power Lora Loader im I2I-Workflow

# LoRA-Presets — privat, nicht in README/Docs
# Format: keyword → Liste von {lora, strength, on}
LORA_PRESETS: dict = {
    "sierra": [
        {"lora": "flux2.9B\\sierra_F2_9B.safetensors",  "strength": 1.0, "on": True},
        {"lora": "flux2.9B\\sns1.2_F2_9B.safetensors", "strength": 1.0, "on": True},
    ],
    # Weitere Presets hier einfügen, z.B.:
    # "snofs": [{"lora": "flux2.9B\\sns1.2_F2_9B.safetensors", "strength": 1.0, "on": True}],
}


def _extract_dimensions(query: str) -> Optional[tuple]:
    """Sucht nach Mustern wie 1920x1080 oder 1024X768 in der Query."""
    import re
    match = re.search(r"(\d{3,4})\s*[xX]\s*(\d{3,4})", query)
    if match:
        w, h = int(match.group(1)), int(match.group(2))
        # Sicherheits-Check: Nicht zu klein, nicht zu groß
        w = max(256, min(2048, w))
        h = max(256, min(2048, h))
        # Runden auf 64 (Zwingend, da der Workflow intern um 0.5 skaliert und LTX Vielfache von 32 braucht)
        w = (w // 64) * 64
        h = (h // 64) * 64
        return (w, h)
    return None


def can_handle(query: str) -> bool:
    lower = query.lower()
    # Direkte Keywords (Bild & Video)
    combined_triggers = TRIGGER_WORDS + VIDEO_TRIGGER_WORDS
    if any(word in lower for word in combined_triggers):
        return True
    # Kombination aus Bild/Video + lokal
    if ("bild" in lower or "video" in lower or "generier" in lower or "erstell" in lower or "animier" in lower) and ("lokal" in lower or "server" in lower):
        return True
    return False


def can_handle_song(query: str) -> bool:
    """Prüft ob die Anfrage Song-Generierung via AceStep triggert."""

    lower = query.lower()
    return any(word in lower for word in SONG_TRIGGER_WORDS)


def execute(query: str, context: dict = None) -> dict:
    """Haupteinstiegspunkt: Extrahiert Prompt, sendet Workflow, holt Bild ab."""
    if not context or "brain" not in context:
        return {"has_payload": False, "html_payload": "", "search_context": ""}

    brain = context["brain"]
    from_telegram = context.get("from_telegram", False)

    # Sicherheits-Check: ComfyUI aktiviert?
    if not getattr(brain, "comfyui_enabled", False):
        sc = ("--- INFO ---\nComfyUI ist in den Einstellungen deaktiviert. "
              "Bitte aktiviere ihn unter '🔑 APIs & Bild → ComfyUI Server' "
              "und starte Trinity neu.\n\n")
        return {"has_payload": False, "html_payload": "", "search_context": sc}

    server_url = getattr(brain, "comfyui_url", "").rstrip("/")
    if not server_url:
        sc = ("--- FEHLER ---\nKeine ComfyUI-Server-URL konfiguriert. "
              "Bitte in den Einstellungen eintragen.\n\n")
        return {"has_payload": False, "html_payload": "", "search_context": sc}

    # Server-Ping
    if not _ping_server(server_url):
        sc = (f"--- FEHLER ---\nDer ComfyUI-Server unter {server_url} ist nicht erreichbar. "
              "Bitte prüfe, ob der Server läuft und die Tailscale-Verbindung aktiv ist.\n\n")
        return {"has_payload": False, "html_payload": "", "search_context": sc}

    # Ordner anlegen
    os.makedirs(MEDIA_INPUT_DIR, exist_ok=True)
    os.makedirs(MEDIA_OUTPUT_DIR, exist_ok=True)

    # Bildprompt aus der Anfrage extrahieren
    image_prompt = _extract_prompt(query, brain)
    print(f"🎨 ComfyUI Prompt: '{image_prompt}'")

    # 1. Musik-Check (T2A)
    if can_handle_song(query):
        print("🎵 Musik-Trigger erkannt -> Umleitung zu execute_t2a")
        return execute_t2a(query, context)

    # 2. Bild/Video-Input Check (I2I / I2V)
    # Wenn der Nutzer explizit ein NEUES Bild will, ignorieren wir das Gedächtnis
    is_new_request = any(word in query.lower() for word in ["neu", "anderes", "fresh", "frisch", "new"])
    
    # Aktueller Input (Upload) hat Vorrang vor Gedächtnis
    input_image_path = context.get("image_path")
    if not input_image_path and not is_new_request:
        input_image_path = getattr(brain, "last_media_path", None)
    
    if input_image_path and os.path.exists(input_image_path):
        is_video = any(word in query.lower() for word in VIDEO_TRIGGER_WORDS)
        if is_video:
            print(f"🎬 Video-Trigger erkannt -> Nutze Bild {input_image_path}")
            return execute_i2v(query, input_image_path, context)
        else:
            # Falls I2I getriggert wird, aber der Nutzer 'neu' sagt, überspringen wir das hier
            # (passiert nur wenn input_image_path aus dem Gedächtnis kam)
            print(f"🖼️ I2I-Trigger erkannt -> Nutze Bild {input_image_path}")
            return execute_i2i(query, input_image_path, context)

    # 3. Standard Text-to-Image (T2I)
    # Auflösung extrahieren (optional)
    dims = _extract_dimensions(query)
    
    # Workflow laden und Prompt injizieren
    workflow_name = getattr(brain, "comfyui_workflow", "Flux2_Klein_T2I_API.json")
    workflow = _load_workflow(workflow_name)
    if not workflow:
        sc = f"--- FEHLER ---\nWorkflow '{workflow_name}' konnte nicht geladen werden.\n\n"
        return {"has_payload": False, "html_payload": "", "search_context": sc}

    workflow = _inject_prompt(workflow, image_prompt)
    
    # Dynamische Maße injizieren falls angegeben
    if dims:
        w, h = dims
        if T2I_WIDTH_NODE in workflow: workflow[T2I_WIDTH_NODE]["inputs"]["value"] = w
        if T2I_HEIGHT_NODE in workflow: workflow[T2I_HEIGHT_NODE]["inputs"]["value"] = h
        print(f"📏 Dynamische Auflösung in T2I injiziert: {w}x{h}")

    # LoRA-Preset erkennen und injizieren (privat, kein Eintrag in Docs)
    lora_preset = _detect_lora_preset(query)
    if lora_preset:
        workflow = _inject_loras(workflow, lora_preset, LORA_NODE_T2I)
        print(f"🎨 LoRA-Preset '{lora_preset}' in T2I injiziert.")

    # An ComfyUI senden
    prompt_id = _queue_prompt(server_url, workflow)
    if not prompt_id:
        sc = "--- FEHLER ---\nKonnte den Workflow nicht an ComfyUI senden.\n\n"
        return {"has_payload": False, "html_payload": "", "search_context": sc}

    print(f"⏳ ComfyUI Job queued (ID: {prompt_id}). Warte auf Ergebnis...")

    # Auf Ergebnis warten (max. 120 Sekunden)
    image_filename = _poll_for_result(server_url, prompt_id, timeout=120)
    if not image_filename:
        sc = "--- FEHLER ---\nDie Bildgenerierung hat zu lange gedauert oder ist fehlgeschlagen.\n\n"
        return {"has_payload": False, "html_payload": "", "search_context": sc}

    # Bild herunterladen und lokal speichern
    local_path = _download_image(server_url, image_filename)
    if not local_path:
        sc = "--- FEHLER ---\nKonnte das fertige Bild nicht vom ComfyUI-Server laden.\n\n"
        return {"has_payload": False, "html_payload": "", "search_context": sc}

    print(f"✅ Bild lokal gespeichert: {local_path}")
    
    # Im Brain merken für Folgeanweisungen
    brain.last_media_path = local_path

    # Telegram: Bild senden (wenn von Telegram angefordert ODER UI+Telegram aktiv)
    telegram_cfg = context.get("telegram_cfg", {})
    if telegram_cfg.get("enabled") and telegram_cfg.get("bot_token") and telegram_cfg.get("chat_id"):
        _send_telegram_photo(local_path, image_prompt, telegram_cfg)

    # UI-Payload bauen (immer, auch wenn von Telegram — Brain zeigt es an wenn has_payload=True)
    html_payload = _build_image_payload(local_path, image_prompt)
    sc = (f"--- COMFYUI BILD ---\nDu hast soeben via lokalem ComfyUI-Server (Flux2 Klein) "
          f"ein Bild zu '{image_prompt}' generiert und es wird nun im Nebenfenster angezeigt. "
          f"Bestätige dem Nutzer kurz, dass das Bild fertig ist.\n\n")

    return {
        "has_payload": not from_telegram,  # Kein UI-Payload wenn rein Telegram-Anfrage
        "html_payload": html_payload,
        "search_context": sc
    }


def execute_i2i(query: str, input_image_path: str, context: dict = None) -> dict:
    """
    Image-to-Image Einstiegspunkt.
    Wird direkt vom Telegram-Listener aufgerufen wenn ein Foto + Text empfangen wird.
    input_image_path: lokaler Pfad zu dem Bild in media/input/
    """
    if not context or "brain" not in context:
        return {"has_payload": False, "html_payload": "", "search_context": ""}

    brain = context["brain"]
    from_telegram = context.get("from_telegram", False)
    telegram_cfg = context.get("telegram_cfg", {})

    if not getattr(brain, "comfyui_enabled", False):
        sc = ("--- INFO ---\nComfyUI ist deaktiviert. "
              "Bitte in den Einstellungen aktivieren.\n\n")
        return {"has_payload": False, "html_payload": "", "search_context": sc}

    server_url = getattr(brain, "comfyui_url", "").rstrip("/")
    if not server_url or not _ping_server(server_url):
        sc = (f"--- FEHLER ---\nComfyUI-Server nicht erreichbar: {server_url}\n\n")
        return {"has_payload": False, "html_payload": "", "search_context": sc}

    os.makedirs(MEDIA_INPUT_DIR, exist_ok=True)
    os.makedirs(MEDIA_OUTPUT_DIR, exist_ok=True)

    # Prompt extrahieren
    image_prompt = _extract_i2i_prompt(query, brain)
    print(f"🎨 I2I Prompt: '{image_prompt}'")

    # Eingabebild auf ComfyUI-Server hochladen
    server_filename = _upload_image_to_comfyui(server_url, input_image_path)
    if not server_filename:
        sc = "--- FEHLER ---\nKonnte das Eingabebild nicht auf den ComfyUI-Server hochladen.\n\n"
        return {"has_payload": False, "html_payload": "", "search_context": sc}

    # I2I-Workflow laden und beide Nodes injizieren
    workflow = _load_workflow(WORKFLOW_I2I)
    if not workflow:
        sc = f"--- FEHLER ---\nWorkflow '{WORKFLOW_I2I}' nicht gefunden.\n\n"
        return {"has_payload": False, "html_payload": "", "search_context": sc}

    workflow = _inject_i2i_inputs(workflow, image_prompt, server_filename)
    
    # Auflösung extrahieren und injizieren
    dims = _extract_dimensions(query)
    if dims:
        w, h = dims
        if I2I_LATENT_NODE in workflow:
            workflow[I2I_LATENT_NODE]["inputs"]["width"] = w
            workflow[I2I_LATENT_NODE]["inputs"]["height"] = h
        if I2I_SCHEDULER_NODE in workflow:
            workflow[I2I_SCHEDULER_NODE]["inputs"]["width"] = w
            workflow[I2I_SCHEDULER_NODE]["inputs"]["height"] = h
        if I2I_MEGAPIXEL_NODE in workflow:
            workflow[I2I_MEGAPIXEL_NODE]["inputs"]["megapixels"] = round(w * h / 1000000.0, 2)
        print(f"📏 Dynamische Auflösung in I2I injiziert: {w}x{h}")

    # LoRA-Preset erkennen und injizieren (privat, kein Eintrag in Docs)
    lora_preset = _detect_lora_preset(query)
    if lora_preset:
        workflow = _inject_loras(workflow, lora_preset, LORA_NODE_I2I)
        print(f"🎨 LoRA-Preset '{lora_preset}' in I2I injiziert.")

    # Job an ComfyUI senden
    prompt_id = _queue_prompt(server_url, workflow)
    if not prompt_id:
        sc = "--- FEHLER ---\nKonnte den I2I-Workflow nicht an ComfyUI senden.\n\n"
        return {"has_payload": False, "html_payload": "", "search_context": sc}

    print(f"⏳ I2I Job queued (ID: {prompt_id}). Warte auf Ergebnis...")

    image_filename = _poll_for_result(server_url, prompt_id, timeout=180)
    if not image_filename:
        sc = "--- FEHLER ---\nI2I-Generierung zu langsam oder fehlgeschlagen.\n\n"
        return {"has_payload": False, "html_payload": "", "search_context": sc}

    local_path = _download_image(server_url, image_filename)
    if not local_path:
        sc = "--- FEHLER ---\nKonnte das I2I-Ergebnis nicht herunterladen.\n\n"
        return {"has_payload": False, "html_payload": "", "search_context": sc}

    print(f"✅ I2I Bild gespeichert: {local_path}")
    
    # Im Brain merken für Folgeanweisungen
    brain.last_media_path = local_path

    # Immer an Telegram senden (I2I kommt immer von Telegram)
    if telegram_cfg.get("enabled") and telegram_cfg.get("bot_token") and telegram_cfg.get("chat_id"):
        _send_telegram_photo(local_path, f"🖌️ {image_prompt}", telegram_cfg)

    # UI-Payload für Trinity-Nebenfenster
    html_payload = _build_image_payload(local_path, f"I2I · {image_prompt}")
    sc = (f"--- COMFYUI I2I ---\nDu hast soeben ein Bild via Flux2 Klein Image-to-Image verarbeitet. "
          f"Prompt: '{image_prompt}'. Das Ergebnis wurde an Telegram gesendet.\n\n")

    return {
        "has_payload": not from_telegram,
        "html_payload": html_payload,
        "search_context": sc
    }


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _ping_server(server_url: str) -> bool:
    """Prüft ob der ComfyUI-Server erreichbar ist."""
    try:
        resp = requests.get(f"{server_url}/system_stats", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def _extract_prompt(query: str, brain) -> str:
    """Nutzt das LLM um den eigentlichen Bildinhalt aus der Anfrage zu extrahieren."""
    result = brain.ask_llm([{
        "role": "user",
        "content": (
            f"Der Nutzer möchte ein Bild generieren. Seine Anfrage: '{query}'\n"
            "Extrahiere daraus den BILDINHALT als englischen Stable-Diffusion-Prompt.\n"
            "Antworte NUR mit dem Prompt (max. 120 Wörter, kein Name wie 'Trinity', keine Erklärung)."
        )
    }]).strip().strip('"')
    return result if len(result) > 5 else query[:120]


def _load_workflow(workflow_name: str) -> Optional[dict]:
    """Lädt das Workflow-JSON aus dem workflows/-Ordner."""
    path = os.path.join(WORKFLOWS_DIR, workflow_name)
    if not os.path.exists(path):
        print(f"⚠️ Workflow nicht gefunden: {path}")
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ Fehler beim Laden des Workflows: {e}")
        return None


def _inject_prompt(workflow: dict, prompt_text: str) -> dict:
    """Injiziert den Prompt-Text in Node 14 (T2I-Workflow: CLIPTextEncode)."""
    wf = copy.deepcopy(workflow)
    node = wf.get(T2I_PROMPT_NODE, {})
    if "inputs" in node:
        node["inputs"]["text"] = prompt_text
        wf[T2I_PROMPT_NODE] = node
        print(f"💉 T2I Prompt in Node {T2I_PROMPT_NODE} injiziert.")
    else:
        print(f"⚠️ Node {T2I_PROMPT_NODE} nicht gefunden.")
    return wf


def _inject_i2i_inputs(workflow: dict, prompt_text: str, server_image_filename: str) -> dict:
    """Injiziert Prompt (Node 6) + Bilddateiname (Node 46) in den I2I-Workflow."""
    wf = copy.deepcopy(workflow)

    # Prompt in Node 6
    prompt_node = wf.get(I2I_PROMPT_NODE, {})
    if "inputs" in prompt_node:
        prompt_node["inputs"]["text"] = prompt_text
        wf[I2I_PROMPT_NODE] = prompt_node
        print(f"💉 I2I Prompt in Node {I2I_PROMPT_NODE} injiziert.")

    # Bilddateiname in Node 46
    image_node = wf.get(I2I_IMAGE_NODE, {})
    if "inputs" in image_node:
        image_node["inputs"]["image"] = server_image_filename
        wf[I2I_IMAGE_NODE] = image_node
        print(f"💉 I2I Bild '{server_image_filename}' in Node {I2I_IMAGE_NODE} injiziert.")

    return wf


def _detect_lora_preset(query: str) -> Optional[str]:
    """Erkennt ein LoRA-Preset-Keyword in der Anfrage. Gibt den Preset-Namen zurück oder None."""
    lower = query.lower()
    for preset_name in LORA_PRESETS:
        if preset_name in lower:
            return preset_name
    return None


def _inject_loras(workflow: dict, preset_name: str, lora_node_id: str) -> dict:
    """
    Injiziert ein LoRA-Preset in den PowerLoraLoader eines Workflows.
    Slot-Namen sind 'lora_1', 'lora_2', ... entsprechend dem rgthree-Format.
    Ungenutzte Slots (> Anzahl der Presets) werden deaktiviert.
    """
    wf = copy.deepcopy(workflow)
    loras = LORA_PRESETS.get(preset_name, [])
    node = wf.get(lora_node_id, {})

    if "inputs" not in node:
        print(f"⚠️ LoRA-Node {lora_node_id} nicht gefunden oder kein 'inputs'-Feld.")
        return wf

    # Bis zu 5 Slots injizieren
    for i in range(1, 6):
        slot_key = f"lora_{i}"
        if i <= len(loras):
            entry = loras[i - 1]
            node["inputs"][slot_key] = {
                "on": entry.get("on", True),
                "lora": entry["lora"],
                "strength": entry.get("strength", 1.0)
            }
            print(f"💉 LoRA Slot {i}: {entry['lora']} (strength={entry.get('strength', 1.0)})")
        elif slot_key in node["inputs"]:
            # Slot deaktivieren wenn vorhanden aber kein LoRA zugewiesen
            node["inputs"][slot_key]["on"] = False

    wf[lora_node_id] = node
    return wf


def _upload_image_to_comfyui(server_url: str, local_image_path: str) -> Optional[str]:
    """Lädt ein lokales Bild auf den ComfyUI-Server hoch. Gibt den Server-Dateinamen zurück."""
    try:
        filename = os.path.basename(local_image_path)

        # Korrekte MIME-Type-Erkennung (nicht blind png annehmen)
        ext = os.path.splitext(filename)[1].lower()
        mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                    ".png": "image/png", ".webp": "image/webp"}
        mime_type = mime_map.get(ext, "application/octet-stream")

        with open(local_image_path, "rb") as f:
            resp = requests.post(
                f"{server_url}/upload/image",
                files={"image": (filename, f, mime_type)},
                data={"overwrite": "true"},
                timeout=30
            )
        if resp.status_code == 200:
            data = resp.json()
            # data.get() schützt NICHT vor null-Werten (nur vor fehlendem Key)
            server_name = data.get("name") or filename
            if not server_name:
                server_name = filename
            print(f"📤 Bild auf ComfyUI hochgeladen: {server_name}")
            return server_name
        else:
            print(f"⚠️ Upload-Fehler: {resp.status_code} – {resp.text[:200]}")
    except Exception as e:
        print(f"⚠️ Fehler beim Bild-Upload: {e}")
    return None


def _extract_i2i_prompt(query: str, brain) -> str:
    """Extrahiert den Bearbeitungs-Prompt aus der Nutzeranfrage für I2I."""
    result = brain.ask_llm([{
        "role": "user",
        "content": (
            f"Der Nutzer hat ein Bild hochgeladen und möchte es bearbeiten. Seine Anweisung: '{query}'\n"
            "Formuliere daraus einen präzisen Stable-Diffusion-Prompt der beschreibt, "
            "WIE das Bild transformiert werden soll.\n"
            "Antworte NUR mit dem englischen Prompt (max. 80 Wörter, keine Erklärung)."
        )
    }]).strip().strip('"')
    return result if len(result) > 5 else query[:80]


def _queue_prompt(server_url: str, workflow: dict) -> Optional[str]:
    """Sendet den Workflow an die ComfyUI API und gibt die prompt_id zurück."""
    try:
        payload = {"prompt": workflow}
        resp = requests.post(f"{server_url}/api/prompt", json=payload, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("prompt_id")
        else:
            print(f"⚠️ ComfyUI Queue-Fehler: {resp.status_code} – {resp.text[:200]}")
    except Exception as e:
        print(f"⚠️ Fehler beim Senden an ComfyUI: {e}")
    return None


def _poll_for_result(server_url: str, prompt_id: str, timeout: int = 120) -> Optional[str]:
    """Pollt /api/history bis das Bild fertig ist. Gibt den Dateinamen zurück."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = requests.get(f"{server_url}/api/history/{prompt_id}", timeout=10)
            if resp.status_code == 200:
                history = resp.json()
                if prompt_id in history:
                    outputs = history[prompt_id].get("outputs", {})
                    for node_id, node_output in outputs.items():
                        images = node_output.get("images", [])
                        if images:
                            filename = images[0].get("filename")
                            if filename:
                                print(f"✅ ComfyUI fertig: {filename}")
                                return filename
        except Exception as e:
            print(f"⚠️ Poll-Fehler: {e}")
        time.sleep(3)
    print("⏰ ComfyUI Timeout — kein Ergebnis nach {timeout}s.")
    return None


def _download_image(server_url: str, filename: str) -> Optional[str]:
    """Lädt das fertige Bild vom ComfyUI-Server herunter und speichert es lokal."""
    try:
        url = f"{server_url}/api/view?filename={filename}"
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200:
            local_name = f"comfyui_{int(time.time())}_{filename}"
            local_path = os.path.join(MEDIA_OUTPUT_DIR, local_name)
            with open(local_path, "wb") as f:
                f.write(resp.content)
            return local_path
        else:
            print(f"⚠️ Download-Fehler: {resp.status_code}")
    except Exception as e:
        print(f"⚠️ Fehler beim Bild-Download: {e}")
    return None


def _send_telegram_photo(image_path: str, caption: str, telegram_cfg: dict):
    """Sendet das generierte Bild als Foto an den Telegram-Chat."""
    try:
        token = telegram_cfg["bot_token"]
        chat_id = telegram_cfg["chat_id"]
        url = f"https://api.telegram.org/bot{token}/sendPhoto"
        with open(image_path, "rb") as photo:
            resp = requests.post(url, data={
                "chat_id": chat_id,
                "caption": f"🎨 {caption}"
            }, files={"photo": photo}, timeout=30)
        if resp.status_code == 200:
            print("📱 Bild erfolgreich an Telegram gesendet.")
        else:
            print(f"⚠️ Telegram-Foto Fehler: {resp.status_code} – {resp.text[:100]}")
    except Exception as e:
        print(f"⚠️ Fehler beim Senden des Telegram-Fotos: {e}")


def _build_image_payload(image_path: str, prompt: str) -> str:
    """Erzeugt das HTML für die Anzeige des generierten Bildes im Trinity-UI."""
    if not image_path:
        return ""
    file_url = f"file://{image_path}"
    return f"""
    <!-- KEEP_OPEN -->
    <!-- IMAGE_PAYLOAD -->
    <h2 style="margin-top: 0; font-weight: 300; border-bottom: 1px solid rgba(255,255,255,0.2); padding-bottom: 10px; font-size: 18px;">
        🖼️ ComfyUI · {prompt[:60]}{'...' if len(prompt) > 60 else ''}
    </h2>
    <img id="mainImg" src="{file_url}"
         style="width: 100%; display: block; border-radius: 10px;"
         onload="
             var w = this.naturalWidth;
             var h = this.naturalHeight;
             if (w > 0 && h > 0) {{
                 window.location.hash = 'imgsize_' + w + '_' + h;
             }}
         ">
    <div style="font-size: 11px; opacity: 0.5; margin-top: 6px; text-align: right;">
        via ComfyUI (Flux2 Klein) · agents/comfyui_agent/media/output/
    </div>
    """


# ===========================================================================
# TEXT-TO-AUDIO (AceStep 1.5)
# ===========================================================================

def execute_t2a(query: str, context: dict = None) -> dict:
    """
    Text-to-Audio Einstiegspunkt (AceStep 1.5).
    Generiert einen Song aus Tags + Lyrics via ComfyUI und sendet ihn
    an Telegram und/oder zeigt ihn im Trinity-UI an.
    """
    if not context or "brain" not in context:
        return {"has_payload": False, "html_payload": "", "search_context": ""}

    brain = context["brain"]
    from_telegram = context.get("from_telegram", False)
    telegram_cfg = context.get("telegram_cfg", {})

    if not getattr(brain, "comfyui_enabled", False):
        sc = ("--- INFO ---\nComfyUI ist deaktiviert. "
              "Bitte in den Einstellungen aktivieren.\n\n")
        return {"has_payload": False, "html_payload": "", "search_context": sc}

    server_url = getattr(brain, "comfyui_url", "").rstrip("/")
    if not server_url or not _ping_server(server_url):
        sc = f"--- FEHLER ---\nComfyUI-Server nicht erreichbar: {server_url}\n\n"
        return {"has_payload": False, "html_payload": "", "search_context": sc}

    os.makedirs(MEDIA_OUTPUT_DIR, exist_ok=True)
    audio_output_dir = os.path.join(MEDIA_OUTPUT_DIR, "audio")
    os.makedirs(audio_output_dir, exist_ok=True)

    # LLM extrahiert Musik-Parameter
    params = _extract_t2a_params(query, brain)
    print(f"🎵 T2A Parameter: style='{params['tags'][:60]}', bpm={params['bpm']}, dur={params['duration']}s")

    # Workflow laden und injizieren
    workflow = _load_workflow(WORKFLOW_T2A)
    if not workflow:
        sc = f"--- FEHLER ---\nWorkflow '{WORKFLOW_T2A}' nicht gefunden.\n\n"
        return {"has_payload": False, "html_payload": "", "search_context": sc}

    workflow = _inject_t2a_inputs(workflow, params)

    # Job senden
    prompt_id = _queue_prompt(server_url, workflow)
    if not prompt_id:
        sc = "--- FEHLER ---\nKonnte den T2A-Workflow nicht an ComfyUI senden.\n\n"
        return {"has_payload": False, "html_payload": "", "search_context": sc}

    print(f"⏳ T2A Job queued (ID: {prompt_id}). Warte auf Ergebnis (~{params['duration']}s)...")

    # Warte etwas länger — Song-Generierung dauert länger als Bildgenerierung
    audio_filename = _poll_for_audio(server_url, prompt_id, timeout=params["duration"] * 3 + 60)
    if not audio_filename:
        sc = "--- FEHLER ---\nSong-Generierung fehlgeschlagen oder Timeout.\n\n"
        return {"has_payload": False, "html_payload": "", "search_context": sc}

    # Audio herunterladen
    local_path = _download_audio(server_url, audio_filename, audio_output_dir)
    if not local_path:
        sc = "--- FEHLER ---\nKonnte das Audio nicht vom ComfyUI-Server laden.\n\n"
        return {"has_payload": False, "html_payload": "", "search_context": sc}

    print(f"✅ Audio gespeichert: {local_path}")

    # Telegram: Audio senden
    if telegram_cfg.get("enabled") and telegram_cfg.get("bot_token") and telegram_cfg.get("chat_id"):
        _send_telegram_audio(local_path, params["tags"], telegram_cfg)

    # UI: HTML5-Audio-Player
    song_title = params.get("title", params["tags"][:50])
    html_payload = _build_audio_payload(local_path, song_title, params)
    sc = (f"--- COMFYUI SONG ---\nDu hast soeben via AceStep 1.5 einen Song generiert: "
          f"'{song_title}'. Stil: {params['tags'][:60]}. "
          f"Er wird im Nebenfenster abgespielt und an Telegram gesendet. "
          f"Bestätige dem Nutzer kurz.\n\n")

    return {
        "has_payload": not from_telegram,
        "html_payload": html_payload,
        "search_context": sc
    }


def _extract_t2a_params(query: str, brain) -> dict:
    """LLM extrahiert alle AceStep-Parameter aus dem Nutzerbefehl."""
    raw = brain.ask_llm([{
        "role": "user",
        "content": (
            f"Der Nutzer möchte einen Song generieren. Anfrage: '{query}'\n"
            "Extrahiere folgende Parameter als JSON:\n"
            "- title: Kurzer Songtitel (deutsch, max 6 Wörter)\n"
            "- tags: Englische Musikstil-Beschreibung (Genre, Instrumente, Stimmung, max 80 Wörter)\n"
            "- lyrics: Deutsche Songtexte (Verse, Chorus; wenn keine angegeben, erfinde passende; max 300 Wörter)\n"
            "- bpm: Tempo (60-140, passend zum Stil)\n"
            "- duration: Länge in Sekunden (60-180)\n"
            "- keyscale: Tonart auf Englisch (z.B. 'C major', 'A minor')\n"
            "- language: Sprache des Lyrics ('de' oder 'en')\n"
            "Antworte NUR mit gültigem JSON, keine Erklärung."
        )
    }]).strip()

    # JSON aus LLM-Antwort parsen (robust gegen Markdown-Codeblöcke)
    import re
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        try:
            params = json.loads(match.group())
            # Defaults für fehlende Felder
            params.setdefault("title", "Unbekannt")
            params.setdefault("tags", "emotional indie pop, acoustic guitar, piano, melancholic")
            params.setdefault("lyrics", "[Verse]\nOhne Worte\n\n[Chorus]\nNur Musik")
            params.setdefault("bpm", 80)
            params.setdefault("duration", 120)
            params.setdefault("keyscale", "C major")
            params.setdefault("language", "de")
            return params
        except Exception:
            pass

    # Fallback
    return {
        "title": "Generierter Song",
        "tags": "emotional indie pop, acoustic guitar, melancholic atmosphere",
        "lyrics": "[Verse]\nOhne Worte\n\n[Chorus]\nNur Musik bleibt",
        "bpm": 80,
        "duration": 120,
        "keyscale": "C major",
        "language": "de"
    }


def _inject_t2a_inputs(workflow: dict, params: dict) -> dict:
    """Injiziert alle Song-Parameter in den T2A-Workflow."""
    wf = copy.deepcopy(workflow)

    # Node 94: TextEncodeAceStepAudio1.5
    encode_node = wf.get(T2A_ENCODE_NODE, {})
    if "inputs" in encode_node:
        encode_node["inputs"]["tags"] = params["tags"]
        encode_node["inputs"]["lyrics"] = params["lyrics"]
        encode_node["inputs"]["bpm"] = int(params.get("bpm", 80))
        encode_node["inputs"]["duration"] = int(params.get("duration", 120))
        encode_node["inputs"]["language"] = params.get("language", "de")
        encode_node["inputs"]["keyscale"] = params.get("keyscale", "C major")
        wf[T2A_ENCODE_NODE] = encode_node
        print(f"💉 T2A Encode-Node {T2A_ENCODE_NODE} injiziert.")

    # Node 98: EmptyAceStep1.5LatentAudio — Länge synchronisieren
    latent_node = wf.get(T2A_LATENT_NODE, {})
    if "inputs" in latent_node:
        latent_node["inputs"]["seconds"] = int(params.get("duration", 120))
        wf[T2A_LATENT_NODE] = latent_node
        print(f"💉 T2A Latent-Node {T2A_LATENT_NODE}: {params['duration']}s")

    return wf


def _poll_for_audio(server_url: str, prompt_id: str, timeout: int = 420) -> Optional[str]:
    """Pollt /api/history bis das Audio fertig ist. Gibt den Dateinamen zurück."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = requests.get(f"{server_url}/api/history/{prompt_id}", timeout=10)
            if resp.status_code == 200:
                history = resp.json()
                if prompt_id in history:
                    outputs = history[prompt_id].get("outputs", {})
                    for node_id, node_output in outputs.items():
                        # Audio-Output kann unter 'audio' oder 'files' liegen
                        for key in ("audio", "files"):
                            items = node_output.get(key, [])
                            if items:
                                filename = items[0].get("filename")
                                if filename:
                                    print(f"✅ ComfyUI Audio fertig: {filename}")
                                    return filename
        except Exception as e:
            print(f"⚠️ Audio-Poll-Fehler: {e}")
        time.sleep(5)
    print(f"⏰ T2A Timeout nach {timeout}s.")
    return None


def _download_audio(server_url: str, filename: str, output_dir: str) -> Optional[str]:
    """Lädt das fertige Audio vom ComfyUI-Server herunter."""
    try:
        # ComfyUI speichert Audio im audio/ Unterordner
        subfolder = "audio" if "/" not in filename else ""
        url = f"{server_url}/api/view?filename={filename}&subfolder={subfolder}&type=output"
        resp = requests.get(url, timeout=60)
        if resp.status_code == 200:
            basename = os.path.basename(filename)
            local_name = f"song_{int(time.time())}_{basename}"
            local_path = os.path.join(output_dir, local_name)
            with open(local_path, "wb") as f:
                f.write(resp.content)
            return local_path
        else:
            print(f"⚠️ Audio-Download-Fehler: {resp.status_code}")
    except Exception as e:
        print(f"⚠️ Fehler beim Audio-Download: {e}")
    return None


def _send_telegram_audio(audio_path: str, caption: str, telegram_cfg: dict):
    """Sendet das generierte Audio als Audiodatei an den Telegram-Chat."""
    try:
        token = telegram_cfg["bot_token"]
        chat_id = telegram_cfg["chat_id"]
        url = f"https://api.telegram.org/bot{token}/sendAudio"
        with open(audio_path, "rb") as audio_file:
            resp = requests.post(url, data={
                "chat_id": chat_id,
                "caption": f"🎵 {caption[:200]}"
            }, files={"audio": audio_file}, timeout=60)
        if resp.status_code == 200:
            print("📱 Audio erfolgreich an Telegram gesendet.")
        else:
            print(f"⚠️ Telegram-Audio Fehler: {resp.status_code} – {resp.text[:100]}")
    except Exception as e:
        print(f"⚠️ Fehler beim Senden des Telegram-Audios: {e}")


def _build_audio_payload(audio_path: str, title: str, params: dict) -> str:
    """Erzeugt einen HTML5-Audio-Player als Trinity-UI-Payload."""
    if not audio_path:
        return ""
    file_url = f"file://{audio_path}"
    bpm = params.get("bpm", "?")
    duration = params.get("duration", "?")
    keyscale = params.get("keyscale", "?")
    tags_short = params.get("tags", "")[:80]
    lyrics_preview = params.get("lyrics", "")[:200].replace("\n", "<br>")

    return f"""
    <!-- KEEP_OPEN -->
    <!-- AUDIO_PAYLOAD -->
    <h2 style="margin-top: 0; font-weight: 300; border-bottom: 1px solid rgba(255,255,255,0.2);
               padding-bottom: 10px; font-size: 18px;">
        🎵 {title}
    </h2>
    <audio controls autoplay style="width: 100%; margin-bottom: 14px; border-radius: 8px;">
        <source src="{file_url}" type="audio/mpeg">
        Dein Browser unterstützt kein Audio.
    </audio>
    <div style="font-size: 12px; opacity: 0.7; line-height: 1.6;">
        <span style="color:#00bfff;">Stil:</span> {tags_short}<br>
        <span style="color:#00bfff;">BPM:</span> {bpm} &nbsp;|&nbsp;
        <span style="color:#00bfff;">Dauer:</span> {duration}s &nbsp;|&nbsp;
        <span style="color:#00bfff;">Tonart:</span> {keyscale}
    </div>
    <details style="margin-top: 12px;">
        <summary style="cursor:pointer; opacity:0.5; font-size:11px;">Lyrics anzeigen</summary>
        <div style="font-size: 12px; line-height: 1.8; margin-top: 8px; opacity: 0.8;">
            {lyrics_preview}{'...' if len(params.get('lyrics','')) > 200 else ''}
        </div>
    </details>
    <div style="font-size: 10px; opacity: 0.4; margin-top: 10px; text-align: right;">
        via ComfyUI · AceStep 1.5 · media/output/audio/
    </div>
    """


# ===========================================================================
# IMAGE-TO-VIDEO (LTX 2.3 I2V)
# ===========================================================================

def can_handle_video(caption: str) -> bool:
    """Prüft ob eine Telegram-Caption einen Video-Workflow triggert."""
    lower = caption.lower()
    return any(word in lower for word in VIDEO_TRIGGER_WORDS)


def execute_i2v(query: str, input_image_path: str, context: dict = None) -> dict:
    """
    Image-to-Video via LTX 2.3.
    Liest Bildabmessungen lokal aus, berechnet 0.7x-Auflösung (÷32),
    injiziert Prompt + Dauer (5-15s) und sendet das Video an Telegram und UI.
    """
    if not context or "brain" not in context:
        return {"has_payload": False, "html_payload": "", "search_context": ""}

    brain = context["brain"]
    from_telegram = context.get("from_telegram", False)
    telegram_cfg = context.get("telegram_cfg", {})

    if not getattr(brain, "comfyui_enabled", False):
        sc = "--- INFO ---\nComfyUI ist deaktiviert.\n\n"
        return {"has_payload": False, "html_payload": "", "search_context": sc}

    server_url = getattr(brain, "comfyui_url", "").rstrip("/")
    if not server_url or not _ping_server(server_url):
        sc = f"--- FEHLER ---\nComfyUI-Server nicht erreichbar: {server_url}\n\n"
        return {"has_payload": False, "html_payload": "", "search_context": sc}

    os.makedirs(MEDIA_INPUT_DIR, exist_ok=True)
    video_output_dir = os.path.join(MEDIA_OUTPUT_DIR, "video")
    os.makedirs(video_output_dir, exist_ok=True)

    # Bildabmessungen lokal auslesen
    img_w, img_h = _get_image_dimensions(input_image_path)
    if img_w == 0 or img_h == 0:
        sc = "--- FEHLER ---\nKonnte Bildabmessungen nicht auslesen.\n\n"
        return {"has_payload": False, "html_payload": "", "search_context": sc}

    # 1.0x Auflösung (Original), auf 32 gerundet
    target_w, target_h = _calc_video_resolution(img_w, img_h, scale=1.0)
    
    # Manuelle Auflösung aus Prompt priorisieren falls angegeben
    manual_dims = _extract_dimensions(query)
    if manual_dims:
        target_w, target_h = manual_dims
        print(f"📏 Manuelle Video-Auflösung erkannt: {target_w}x{target_h}")
    else:
        print(f"📐 Bild: {img_w}×{img_h} → Video: {target_w}×{target_h} (1.0x)")

    # Parameter via LLM extrahieren
    params = _extract_i2v_params(query, brain)
    
    # LTX-kompatible Dauer berechnen (8N+1 Frames bei 24 FPS)
    params["duration_ltx"] = _calc_ltx_duration(params["duration"], fps=24.0)
    
    print(f"🎬 I2V: '{params['motion_prompt'][:60]}', {params['duration_ltx']:.3f}s (8N+1)")

    # Bild auf ComfyUI hochladen
    server_filename = _upload_image_to_comfyui(server_url, input_image_path)
    if not server_filename:
        sc = "--- FEHLER ---\nKonnte das Eingabebild nicht hochladen.\n\n"
        return {"has_payload": False, "html_payload": "", "search_context": sc}

    print(f"📤 Server-Dateiname nach Upload: '{server_filename}'")

    # Workflow laden und injizieren
    workflow = _load_workflow(WORKFLOW_I2V)
    if not workflow:
        sc = f"--- FEHLER ---\nWorkflow '{WORKFLOW_I2V}' nicht gefunden.\n\n"
        return {"has_payload": False, "html_payload": "", "search_context": sc}

    try:
        workflow = _inject_i2v_inputs(workflow, server_filename, target_w, target_h, params)
    except ValueError as e:
        sc = f"--- FEHLER ---\n{e}\n\n"
        return {"has_payload": False, "html_payload": "", "search_context": sc}

    # Job senden
    prompt_id = _queue_prompt(server_url, workflow)
    if not prompt_id:
        sc = "--- FEHLER ---\nKonnte den I2V-Workflow nicht senden.\n\n"
        return {"has_payload": False, "html_payload": "", "search_context": sc}

    print(f"⏳ I2V Job queued (ID: {prompt_id}), ~{params['duration']}s Video...")

    # Auf Ergebnis warten (Video dauert viel länger als Bild)
    timeout = max(300, params["duration"] * 25)
    video_filename = _poll_for_video(server_url, prompt_id, timeout=timeout)
    if not video_filename:
        sc = "--- FEHLER ---\nVideo-Generierung fehlgeschlagen oder Timeout.\n\n"
        return {"has_payload": False, "html_payload": "", "search_context": sc}

    local_path = _download_video(server_url, video_filename, video_output_dir)
    if not local_path:
        sc = "--- FEHLER ---\nKonnte das Video nicht herunterladen.\n\n"
        return {"has_payload": False, "html_payload": "", "search_context": sc}

    print(f"✅ Video gespeichert: {local_path}")

    # Telegram: Video senden
    if telegram_cfg.get("enabled") and telegram_cfg.get("bot_token") and telegram_cfg.get("chat_id"):
        _send_telegram_video(local_path, params["motion_prompt"], telegram_cfg,
                             target_w, target_h, params["duration"])

    # UI: HTML5-Video-Player
    html_payload = _build_video_payload(local_path, params, target_w, target_h)
    sc = (f"--- COMFYUI VIDEO ---\nDu hast soeben via LTX 2.3 ein Kurzvideo generiert "
          f"({params['duration']}s, {target_w}×{target_h}). "
          f"Es wird im Nebenfenster abgespielt und an Telegram gesendet. "
          f"Bestätige dem Nutzer kurz.\n\n")

    return {
        "has_payload": not from_telegram,
        "html_payload": html_payload,
        "search_context": sc
    }


def _get_image_dimensions(image_path: str) -> tuple:
    """Liest Breite und Höhe eines Bildes aus (via Pillow)."""
    try:
        from PIL import Image
        with Image.open(image_path) as img:
            return img.width, img.height
    except ImportError:
        # Fallback: struct-basiertes PNG/JPEG Lesen
        try:
            import struct
            with open(image_path, "rb") as f:
                header = f.read(24)
            if header[:8] == b'\x89PNG\r\n\x1a\n':
                w, h = struct.unpack('>II', header[16:24])
                return w, h
            elif header[:2] == b'\xff\xd8':  # JPEG
                f = open(image_path, "rb")
                f.seek(0)
                while True:
                    marker = f.read(2)
                    if marker[1] in (0xC0, 0xC2):
                        f.read(3)
                        h, w = struct.unpack('>HH', f.read(4))
                        f.close()
                        return w, h
                    else:
                        size = struct.unpack('>H', f.read(2))[0]
                        f.seek(size - 2, 1)
        except Exception:
            pass
    except Exception as e:
        print(f"⚠️ Fehler beim Lesen der Bildgröße: {e}")
    return 0, 0


def _calc_ltx_frames(duration_s: int, fps: int = 25) -> int:
    """Berechnet die LTX-kompatible Frame-Anzahl.
    
    LTX 2.3 benötigt:
    - frames = 8 * N + 1 (wegen Temporal VAE mit Faktor 8)
    - latent_frames = (frames - 1) / 8  muss durch 4 teilbar sein (LTXVChunkFeedForward)
    - => frames = 8 * (4 * k) + 1 = 32 * k + 1, k >= 1
    """
    # Zielframes als Annäherung
    target = duration_s * fps
    # Aufrunden auf nächste gültige Frames-Anzahl (32*k + 1)
    k = max(1, (target - 1 + 31) // 32)  # ceil-Division
    frames = 32 * k + 1
    # Clamp auf vernünftigen Bereich (min 33 Frames, max 1025 ~= 41s bei 25fps)
    frames = max(33, min(1025, frames))
    return frames


def _calc_video_resolution(img_w: int, img_h: int, scale: float = 1.0) -> tuple:
    """Berechnet die Zielauflösung: scale * Originalgröße, auf 32 gerundet, max 1536."""
    w = round((img_w * scale) / 32) * 32
    h = round((img_h * scale) / 32) * 32
    # Clamp: min 256, max 1536 (LTX-Limit für Stabilität)
    w = max(256, min(1536, w))
    h = max(256, min(1536, h))
    return w, h


def _calc_ltx_duration(target_sec: float, fps: float = 24.0) -> float:
    """
    Berechnet die exakte Sekundenzahl, die zu einer LTX-kompatiblen
    Frame-Anzahl (8N + 1) führt.
    Beispiel: 7s bei 24fps = 168 frames -> nächstes 8N+1 ist 169 -> 169/24 = 7.0416s
    """
    target_frames = round(target_sec * fps)
    # Nächste Zahl der Form 8n + 1
    valid_frames = round((target_frames - 1) / 8) * 8 + 1
    # Sicherheits-Check: Falls wir unter 1 gelandet sind
    if valid_frames < 1: valid_frames = 9 
    return float(valid_frames) / fps


def _extract_i2v_params(query: str, brain) -> dict:
    """LLM extrahiert Motion-Prompt und Dauer (5-15s) aus der Nutzeranfrage."""
    raw = brain.ask_llm([{
        "role": "user",
        "content": (
            f"Der Nutzer möchte ein Kurzvideo aus einem Bild generieren. Anfrage: '{query}'\n"
            "Extrahiere als JSON:\n"
            "- motion_prompt: Englischer Beschreibungstext der Bewegung/Animation "
            "(cinematic, smooth camera, was soll sich bewegen/wie, max 60 Wörter)\n"
            "- duration: Videolänge in Sekunden (Ganzzahl, min 5, max 15; "
            "wenn nicht angegeben: 7; bevorzuge 5-10s)\n"
            "Antworte NUR mit gültigem JSON."
        )
    }]).strip()

    import re
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        try:
            params = json.loads(match.group())
            # Dauer validieren und klemmen
            dur = int(params.get("duration", 7))
            params["duration"] = max(5, min(15, dur))
            params.setdefault("motion_prompt",
                              "smooth cinematic movement, subtle ambient motion, high quality")
            return params
        except Exception:
            pass
    return {
        "motion_prompt": "smooth cinematic movement, subtle ambient motion, high quality",
        "duration": 7
    }


def _inject_i2v_inputs(workflow: dict, server_filename: str,
                        width: int, height: int, params: dict) -> dict:
    """
    Injiziert nur Eingabebild + Prompt in den LTX-2.3-Workflow.
    Auflösung, Frame-Anzahl und FPS bleiben unverändert (Workflow-Defaults
    funktionieren direkt in ComfyUI und werden nicht überschrieben).
    """
    if not server_filename or not isinstance(server_filename, str):
        raise ValueError(
            f"I2V-Abort: server_filename ist ungültig ({server_filename!r}). "
            "Bild-Upload wahrscheinlich fehlgeschlagen."
        )

    wf = copy.deepcopy(workflow)

    # Node 45: LoadImage "First Frame" — Eingabebild setzen
    img_node = wf.get(I2V_IMAGE_NODE, {})
    if "inputs" in img_node:
        img_node["inputs"]["image"] = server_filename
        wf[I2V_IMAGE_NODE] = img_node
        print(f"💉 I2V Bild '{server_filename}' → Node {I2V_IMAGE_NODE}")
    else:
        print(f"⚠️ I2V: Node {I2V_IMAGE_NODE} hat kein 'inputs'-Feld — Bild NICHT injiziert!")

    # Node 66: Width — Auflösung injizieren damit das Bild nicht "kleiner gemacht" wird
    w_node = wf.get(I2V_WIDTH_NODE, {})
    if "inputs" in w_node:
        w_node["inputs"]["value"] = width
        wf[I2V_WIDTH_NODE] = w_node
        print(f"💉 I2V Breite {width} → Node {I2V_WIDTH_NODE}")

    # Node 67: Height
    h_node = wf.get(I2V_HEIGHT_NODE, {})
    if "inputs" in h_node:
        h_node["inputs"]["value"] = height
        wf[I2V_HEIGHT_NODE] = h_node
        print(f"💉 I2V Höhe {height} → Node {I2V_HEIGHT_NODE}")

    # Node 68: Duration (Sekunden)
    # Wir injizieren den berechneten Float-Wert für 8N+1 Frames
    duration_val = params.get("duration_ltx", params.get("duration", 7.0))
    l_node = wf.get(I2V_LENGTH_NODE, {})
    if "inputs" in l_node:
        l_node["inputs"]["value"] = duration_val
        wf[I2V_LENGTH_NODE] = l_node
        print(f"💉 I2V Dauer {duration_val:.4f}s → Node {I2V_LENGTH_NODE}")

    # Node 173: Positive Prompt — Bewegungsbeschreibung injizieren
    p_node = wf.get(I2V_PROMPT_NODE, {})
    if "inputs" in p_node:
        prompt_val = params.get("motion_prompt")
        if not prompt_val or not isinstance(prompt_val, str):
            prompt_val = "smooth cinematic movement, subtle ambient motion, high quality"
        p_node["inputs"]["value"] = str(prompt_val)
        wf[I2V_PROMPT_NODE] = p_node
        print(f"💉 I2V Prompt → Node {I2V_PROMPT_NODE}: '{prompt_val[:60]}'")

    # Auflösung und Länge werden NICHT verändert — Workflow-Defaults bleiben erhalten
    print(f"ℹ️  I2V: Größe + Dauer aus Workflow-JSON übernommen (kein Override).")

    return wf


def _poll_for_video(server_url: str, prompt_id: str, timeout: int = 300) -> Optional[str]:
    """Pollt /api/history bis das Video fertig ist. VHS_VideoCombine speichert unter 'gifs'."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = requests.get(f"{server_url}/api/history/{prompt_id}", timeout=10)
            if resp.status_code == 200:
                history = resp.json()
                if prompt_id in history:
                    outputs = history[prompt_id].get("outputs", {})
                    for node_id, node_output in outputs.items():
                        # VHS_VideoCombine gibt unter 'gifs' oder 'files' aus
                        for key in ("gifs", "files", "videos"):
                            items = node_output.get(key, [])
                            if items:
                                filename = items[0].get("filename")
                                if filename:
                                    print(f"✅ I2V fertig: {filename}")
                                    return filename
        except Exception as e:
            print(f"⚠️ Video-Poll-Fehler: {e}")
        time.sleep(6)
    print(f"⏰ I2V Timeout nach {timeout}s.")
    return None


def _download_video(server_url: str, filename: str, output_dir: str) -> Optional[str]:
    """Lädt das fertige Video vom ComfyUI-Server herunter."""
    try:
        # VHS speichert im video/ Unterordner
        subfolder = "video" if "/" not in filename else ""
        url = f"{server_url}/api/view?filename={filename}&subfolder={subfolder}&type=output"
        resp = requests.get(url, timeout=120)
        if resp.status_code == 200:
            basename = os.path.basename(filename)
            local_name = f"video_{int(time.time())}_{basename}"
            local_path = os.path.join(output_dir, local_name)
            with open(local_path, "wb") as f:
                f.write(resp.content)
            return local_path
        else:
            print(f"⚠️ Video-Download-Fehler: {resp.status_code}")
    except Exception as e:
        print(f"⚠️ Fehler beim Video-Download: {e}")
    return None


def _send_telegram_video(video_path: str, caption: str, telegram_cfg: dict,
                          width: int, height: int, duration: int):
    """Sendet das generierte Video via sendVideo an Telegram."""
    try:
        token = telegram_cfg["bot_token"]
        chat_id = telegram_cfg["chat_id"]
        url = f"https://api.telegram.org/bot{token}/sendVideo"
        with open(video_path, "rb") as vf:
            resp = requests.post(url, data={
                "chat_id": chat_id,
                "caption": f"🎬 {caption[:200]}",
                "width": width,
                "height": height,
                "duration": duration,
                "supports_streaming": True
            }, files={"video": vf}, timeout=120)
        if resp.status_code == 200:
            print("📱 Video erfolgreich an Telegram gesendet.")
        else:
            print(f"⚠️ Telegram-Video Fehler: {resp.status_code} – {resp.text[:100]}")
    except Exception as e:
        print(f"⚠️ Fehler beim Senden des Telegram-Videos: {e}")


def _build_video_payload(video_path: str, params: dict, width: int, height: int) -> str:
    """Erzeugt einen HTML5-Video-Player als Trinity-UI-Payload."""
    if not video_path:
        return ""
    file_url = f"file://{video_path}"
    duration = params.get("duration", "?")
    motion = params.get("motion_prompt", "")[:80]
    aspect = f"{width}:{height}"

    return f"""
    <!-- KEEP_OPEN -->
    <!-- VIDEO_PAYLOAD -->
    <h2 style="margin-top: 0; font-weight: 300; border-bottom: 1px solid rgba(255,255,255,0.2);
               padding-bottom: 10px; font-size: 18px;">
        🎬 LTX 2.3 · {duration}s · {width}×{height}
    </h2>
    <video controls autoplay loop
           style="width: 100%; border-radius: 10px; display: block; margin-bottom: 12px;"
           width="{width}" height="{height}">
        <source src="{file_url}" type="video/mp4">
        Dein Browser unterstützt kein Video.
    </video>
    <div style="font-size: 12px; opacity: 0.7; line-height: 1.6;">
        <span style="color:#00bfff;">Bewegung:</span> {motion}<br>
        <span style="color:#00bfff;">Auflösung:</span> {width}×{height} &nbsp;|&nbsp;
        <span style="color:#00bfff;">Dauer:</span> {duration}s &nbsp;|&nbsp;
        <span style="color:#00bfff;">Format:</span> H.264 MP4
    </div>
    <div style="font-size: 10px; opacity: 0.4; margin-top: 10px; text-align: right;">
        via ComfyUI · LTX 2.3 I2V · media/output/video/
    </div>
    """

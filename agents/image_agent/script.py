import os
import time
import requests

def can_handle(query: str) -> bool:
    router_text = query.lower()
    return any(word in router_text for word in ["infografik", "grafik", "visualisier", "schaubild", "illustration"]) or \
         (any(word in router_text for word in ["bild", "zeichnung"]) and any(cmd in router_text for cmd in ["erstell", "mach", "generier", "zeig"]))

def execute(query: str, context: dict = None) -> dict:
    if not context or "brain" not in context:
        return {"has_payload": False, "html_payload": "", "search_context": ""}
        
    brain = context["brain"]
    
    if not brain.fal_key or not str(brain.fal_key).strip():
        search_context = "--- INFO ---\nDer Nutzer hat um ein Bild gebeten, aber in der Konfiguration ist kein fal.ai API-Key hinterlegt. Bitte weise den Nutzer freundlich darauf hin, dass er den Key erst in den Einstellungen eintragen muss (Tipp: 'Trinity, öffne Einstellungen').\n\n"
        return {"has_payload": False, "html_payload": "", "search_context": search_context}
        
    if len(query) < 15:
        print(f"⚠️ Bild-Trigger ignoriert: Query zu kurz ({len(query)} Zeichen).")
        return {"has_payload": False, "html_payload": "", "search_context": ""}
    
    print(f"🚀 Starte Bildgenerierung für: '{query[:50]}'")
    
    # Extrahiere das Thema
    prompt = brain.ask_llm([{"role": "user", "content": 
        f"Der Nutzer hat folgendes gesagt: '{query}'\n"
        f"Extrahiere daraus das THEMA für ein Schaubild/Infografik.\n"
        f"Antworte NUR mit dem Thema (max 10 Wörter, keine Erklärung, kein Name wie 'Trinity')."
    }]).strip('" \n.')
    print(f"🎨 Extrahiertes Bildthema: '{prompt}'")
    
    if len(prompt) < 3:
        prompt = query[:80]
    
    # Prompt-Tuning für einfache, deutsche Metapherbilder
    image_prompt = (f"Einfaches, leicht verständliches Schaubild oder Metapherbild zum Thema: {prompt}. "
                    f"Minimalistisches Design, klare Struktur, weißer Hintergrund, AUSSCHLIESSLICH deutscher Text. "
                    f"Muss in einer Präsentation in kurzer Zeit erfassbar sein. "
                    f"KEINE hochkomplexen Diagramme, außer explizit gefordert. "
                    f"DO NOT include any names like '{brain.agent_name}'.")

    img_path = _generate_image_fal(image_prompt, brain)
    
    if img_path:
        html_payload = _build_image_payload(img_path)
        search_context = f"--- IMAGE GENERATION ---\nDu hast soeben ein Schaubild zu '{prompt}' generiert. Bestätige dem Nutzer, dass er das Bild nun im Nebenfenster sehen kann und biete an, Details dazu zu erklären.\n\n"
        return {
            "has_payload": True,
            "html_payload": html_payload,
            "search_context": search_context
        }
    else:
        search_context = "--- FEHLER ---\nDie Bildgenerierung ist fehlgeschlagen. Bitte entschuldige dich beim Nutzer.\n\n"
        return {"has_payload": False, "html_payload": "", "search_context": search_context}

def _generate_image_fal(prompt, brain):
    """Erzeugt ein Bild mit fal.ai und speichert es lokal."""
    print(f"🎨 Generiere Bild via {brain.image_primary} für '{prompt[:40]}...'")
    url = f"https://fal.run/{brain.image_primary}"
    headers = {
        "Authorization": f"Key {brain.fal_key}",
        "Content-Type": "application/json"
    }
    data = {
        "prompt": prompt,
        "image_size": "landscape_16_9"
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=120)
        
        if response.status_code != 200:
            print(f"⚠️ Primary Modell fehlgeschlagen ({response.status_code}). Nutze Fallback ({brain.image_fallback})...")
            url = f"https://fal.run/{brain.image_fallback}"
            response = requests.post(url, headers=headers, json=data, timeout=120)

        if response.status_code == 200:
            result = response.json()
            image_url = result.get("images", [{}])[0].get("url")
            if image_url:
                img_data = requests.get(image_url).content
                filename = f"gen_{int(time.time())}.png"
                local_path = os.path.join(brain.gen_images_dir, filename)
                with open(local_path, "wb") as f:
                    f.write(img_data)
                print(f"✅ Bild gespeichert: {local_path}")
                return local_path
        else:
            print(f"⚠️ Fal.ai Fehler ({response.status_code}): {response.text}")
    except Exception as e:
        print(f"⚠️ Fal.ai Fehler: {e}")
    return None

def _build_image_payload(image_path):
    """Erzeugt das HTML für die Anzeige des generierten Bildes – Fenster passt sich an Bildgröße an."""
    if not image_path: return ""
    file_url = f"file://{image_path}"
    html = f"""
    <!-- KEEP_OPEN -->
    <!-- IMAGE_PAYLOAD -->
    <img id="mainImg" src="{file_url}"
         style="width: 100%; display: block; border-radius: 10px;"
         onload="
             var w = this.naturalWidth;
             var h = this.naturalHeight;
             if (w > 0 && h > 0) {{
                 window.location.hash = 'imgsize_' + w + '_' + h;
             }}
         ">
    <div style="font-size: 11px; opacity: 0.5; margin-top: 6px; text-align: right;">gen_images/</div>
    """
    return html

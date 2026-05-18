import os
import time
import requests

def can_handle(query: str) -> bool:
    router_text = query.lower()
    # Wenn 'lokal' oder 'server' oder 'comfyui' oder 'flux render' oder 'sierra' vorkommt, soll ComfyUI-Agent übernehmen
    if any(word in router_text for word in ["lokal", "server", "comfyui", "flux render", "sierra"]):
        return False
        
    # Wenn Anzeichen für echte Datenverarbeitung / Pyodide / mathematische Berechnungen vorliegen,
    # blockieren wir den Image-Agent, damit die Sandbox rechnet. Rein konzeptionelle Erklärungsbilder
    # (z. B. "Schaubild zu einer Regression") bleiben weiterhin voll funktionsfähig!
    ds_keywords = [
        "csv", "datensatz", "dataset", "pandas", "pyodide", "dataframe",
        "python code", "führe aus", "berechne", "berechn", "integral", "ableitung", "sympy",
        "http://", "https://"
    ]
    if any(ds in router_text for ds in ds_keywords):
        return False
        
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
    
    import json
    index_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "memory", "images_index.json")
    
    # Lade existierende Bilder
    existing_images = []
    if os.path.exists(index_file):
        try:
            with open(index_file, "r", encoding="utf-8") as f:
                existing_images = json.load(f)
        except Exception:
            pass
            
    if existing_images:
        images_context = "\n".join([f"ID {i}: {img.get('topic', 'Unbekannt')}" for i, img in enumerate(existing_images)])
        mem_prompt = [
            {"role": "system", "content": "Du analysierst einen Nutzerbefehl bezüglich eines Schaubilds. Entscheide, ob der Nutzer ein GANZ NEUES Bild generieren will, oder ob er ein BEREITS EXISTIERENDES Bild NOCHMAL sehen möchte. Antworte NUR mit der ID des Bildes (Zahl) ODER mit 'NEU'."},
            {"role": "user", "content": f"Bestehende Bilder:\n{images_context}\n\nNutzerbefehl: '{query}'\n\nAntwort:"}
        ]
        decision = brain.ask_llm(mem_prompt).strip().upper()
        if decision.isdigit() and int(decision) < len(existing_images):
            img_data = existing_images[int(decision)]
            img_path = img_data.get("path")
            topic = img_data.get("topic")
            print(f"♻️ Zeige existierendes Bild aus Asset-Memory: {topic}")
            html_payload = _build_image_payload(img_path, topic)
            search_context = f"--- IMAGE MEMORY ---\nDu hast dem Nutzer soeben das bereits bekannte Schaubild zum Thema '{topic}' erneut auf den Bildschirm geholt. Erwähne kurz, dass du es wieder hervorgeholt hast.\n\n"
            return {"has_payload": True, "html_payload": html_payload, "search_context": search_context}
    
    print(f"🚀 Starte NEUE Bildgenerierung für: '{query[:50]}'")
    
    # Extrahiere das Thema
    prompt = brain.ask_llm([{"role": "user", "content": 
        f"Der Nutzer hat folgendes gesagt: '{query}'\n"
        f"Extrahiere daraus das THEMA für ein NEUES Schaubild/Infografik.\n"
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
        # Im Index speichern
        existing_images.append({"path": img_path, "topic": prompt, "timestamp": time.time()})
        os.makedirs(os.path.dirname(index_file), exist_ok=True)
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(existing_images, f, indent=2, ensure_ascii=False)
            
        html_payload = _build_image_payload(img_path, prompt)
        search_context = f"--- IMAGE GENERATION ---\nDu hast soeben ein NEUES Schaubild zu '{prompt}' generiert. Bestätige dem Nutzer, dass er das Bild nun im Nebenfenster sehen kann und biete an, Details dazu zu erklären.\n\n"
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

def _build_image_payload(image_path, prompt):
    """Erzeugt das HTML für die Anzeige des generierten Bildes – Fenster passt sich an Bildgröße an."""
    if not image_path: return ""
    file_url = f"file://{image_path}"
    html = f"""
    <!-- KEEP_OPEN -->
    <!-- IMAGE_PAYLOAD -->
    <h2 style="margin-top: 0; font-weight: 300; border-bottom: 1px solid rgba(255,255,255,0.2); padding-bottom: 10px; font-size: 18px;">🎨 {prompt}</h2>
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

import requests
import json
import os
import subprocess
import shutil
import re
import time

class TrinityBrain:
    def __init__(self):
        # Konfiguration aus Datei laden
        self.config_path = os.path.join(os.path.dirname(__file__), "config.json")
        self.soul_path = os.path.join(os.path.dirname(__file__), "Soul.md")
        self.user_path = os.path.join(os.path.dirname(__file__), "User.md")
        self.gen_images_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "gen_images")
        os.makedirs(self.gen_images_dir, exist_ok=True)
        
        self.rag_chunks = []
        self.rag_embeddings = None
        self.rag_model = None

        self.load_config()
        self._load_rag_index()

        # Soul + User einmalig laden und cachen (nicht bei jedem Request neu lesen)
        self._soul_cache = self.get_file_content(self.soul_path, "Du bist Trinity, ein KI-Assistent.")
        self._user_cache = self.get_file_content(self.user_path, "Der Nutzer ist Mat Max.")

    def load_config(self):
        """Lädt die Konfiguration aus der config.json."""
        try:
            if not os.path.exists(self.config_path):
                print(f"⚠️ config.json nicht gefunden bei {self.config_path}")
                return

            with open(self.config_path, "r") as f:
                config = json.load(f)
            
            self.use_local_llm = config["llm"]["use_local"]
            if self.use_local_llm:
                self.url = config["llm"]["local_url"]
                self.model = config["llm"]["local_model"]
                self.api_key = "lm-studio"
            else:
                self.url = config["llm"]["remote_url"]
                self.model = config["llm"]["remote_model"]
                self.api_key = config["llm"]["api_key"]
            
            self.tavily_key = config["apis"]["tavily"]
            self.fal_key = config["apis"]["fal_ai"]
            
            # Persona
            persona = config.get("persona", {})
            self.agent_name = persona.get("agent_name", "Trinity")
            
            # Bild-Modelle
            image = config.get("image", {})
            self.image_primary = image.get("primary_model", "fal-ai/nano-banana-2")
            self.image_fallback = image.get("fallback_model", "fal-ai/nano-banana-pro")
            
            print("⚙️ Konfiguration geladen ✓")
        except Exception as e:
            print(f"⚠️ Fehler beim Laden der config.json: {e}")

    def _load_rag_index(self):
        """Lädt den vorberechneten RAG-Index. Baut ihn neu, falls neue PDFs vorhanden sind."""
        rag_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "RAG")
        index_dir = os.path.join(rag_dir, "index")
        
        if not os.path.isdir(rag_dir):
            print("📚 RAG-Ordner nicht gefunden, Wissensbasis deaktiviert.")
            return

        # Prüfe ob neue PDFs hinzugekommen sind seit letztem Index-Build
        needs_rebuild = False
        chunks_path = os.path.join(index_dir, "chunks.json")
        embeddings_path = os.path.join(index_dir, "embeddings.npy")
        meta_path = os.path.join(index_dir, "meta.json")

        if not all(os.path.exists(p) for p in [chunks_path, embeddings_path, meta_path]):
            needs_rebuild = True
        else:
            # Vergleiche PDF-Liste mit indexierten Quellen
            current_pdfs = sorted([f for f in os.listdir(rag_dir) if f.lower().endswith('.pdf')])
            try:
                import json as _json
                with open(meta_path, "r") as f:
                    meta = _json.load(f)
                indexed_sources = sorted(meta.get("sources", []))
                current_sources = sorted([f.replace('.pdf', '') for f in current_pdfs])
                if indexed_sources != current_sources:
                    print(f"📚 Neue Dokumente erkannt! Baue Index neu...")
                    needs_rebuild = True
                # Prüfe auch ob eine PDF neuer ist als der Index
                index_time = os.path.getmtime(embeddings_path)
                for pdf in current_pdfs:
                    if os.path.getmtime(os.path.join(rag_dir, pdf)) > index_time:
                        print(f"📚 {pdf} wurde aktualisiert! Baue Index neu...")
                        needs_rebuild = True
                        break
            except Exception:
                needs_rebuild = True

        if needs_rebuild:
            print("📚 Starte automatischen Index-Build...")
            build_script = os.path.join(rag_dir, "build_index.py")
            if os.path.exists(build_script):
                try:
                    result = subprocess.run(
                        ["python3", build_script],
                        capture_output=True, text=True, timeout=300
                    )
                    if result.returncode != 0:
                        print(f"⚠️ Index-Build fehlgeschlagen: {result.stderr[:200]}")
                        return
                except subprocess.TimeoutExpired:
                    print("⚠️ Index-Build Timeout (>5min)")
                    return
            else:
                print("⚠️ build_index.py nicht gefunden. Bitte erst ausführen.")
                return

        # Index laden
        try:
            import json as _json
            import numpy as np

            with open(chunks_path, "r", encoding="utf-8") as f:
                self.rag_chunks = _json.load(f)
            raw_embeddings = np.load(embeddings_path).astype(np.float32)

            # Embeddings EINMALIG normalisieren → bei jeder Query nur noch Dot-Product nötig
            norms = np.linalg.norm(raw_embeddings, axis=1, keepdims=True)
            norms = np.maximum(norms, 1e-10)
            self.rag_embeddings = (raw_embeddings / norms).astype(np.float32)
            # NaN/Inf durch leere Chunks bereinigen
            self.rag_embeddings = np.nan_to_num(self.rag_embeddings, nan=0.0, posinf=0.0, neginf=0.0)

            with open(meta_path, "r") as f:
                meta = _json.load(f)

            sources = meta.get("sources", [])
            print(f"📚 RAG-Index geladen: {len(self.rag_chunks)} Chunks aus {len(sources)} Dokumenten ({', '.join(sources)})")
            # Modell wird LAZY geladen – erst beim ersten RAG-Aufruf
        except Exception as e:
            print(f"⚠️ RAG-Index laden fehlgeschlagen: {e}")

    def _load_rag_model(self):
        """Lädt das Embedding-Modell lazy (erst beim ersten RAG-Aufruf)."""
        if self.rag_model is not None:
            return True
        try:
            from sentence_transformers import SentenceTransformer
            print("📚 Lade RAG-Modell (erstmalig)...")
            self.rag_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
            print("📚 RAG-Modell geladen ✓")
            return True
        except ImportError:
            print("⚠️ sentence-transformers nicht installiert. RAG-Suche deaktiviert.")
            return False

    def retrieve_rag(self, query, top_k=3, max_chars=2000):
        """Findet die semantisch relevantesten Chunks via Cosine Similarity (~50ms pro Query)."""
        if not self.rag_chunks or self.rag_embeddings is None:
            return ""

        if not self._load_rag_model():
            return ""

        import numpy as np
        # Query einbetten & normalisieren (Cosine Similarity)
        query_emb = self.rag_model.encode(query, convert_to_numpy=True).astype(np.float32)
        norm = np.linalg.norm(query_emb)
        if norm > 0:
            query_emb /= norm

        if self.rag_embeddings is None:
            return ""

        # Score-Berechnung (Dot-Product auf normalisierten Vektoren = Cosine Sim)
        similarities = np.dot(self.rag_embeddings, query_emb)
        
        # Top-K Chunks finden
        indices = np.argsort(similarities)[-top_k:][::-1]
        
        results = []
        for idx in indices:
            score = float(similarities[idx])
            if score > 0.3: # Mindest-Ähnlichkeit
                chunk = self.rag_chunks[idx]
                results.append(f"[QUELLE: {chunk['source']}]\n{chunk['text']}")
        
        return "\n\n".join(results)[:max_chars]

    def ask_llm(self, messages):
        """Hilfsmethode für interne LLM-Aufrufe (z.B. Context Enrichment)."""
        headers = {"Content-Type": "application/json"}
        data = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0 # Für präzise Fakten/Begriffe
        }
        try:
            resp = requests.post(self.url, headers=headers, json=data, timeout=30)
            if resp.status_code == 200:
                msg = resp.json()['choices'][0]['message']
                # Qwen3-Fix: Fallback auf reasoning_content wenn content leer
                return (msg.get('content') or msg.get('reasoning_content') or '').strip()
        except Exception as e:
            print(f"⚠️ ask_llm Fehler: {e}")
        return ""

    def get_file_content(self, path, fallback=""):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return fallback

    def generate_image_fal(self, prompt, title="Grafik"):
        """Erstellt ein Bild mit fal.ai und speichert es lokal."""
        print(f"🎨 Generiere Bild via {self.image_primary} für '{prompt[:40]}...'")
        url = f"https://fal.run/{self.image_primary}"
        headers = {
            "Authorization": f"Key {self.fal_key}",
            "Content-Type": "application/json"
        }
        data = {
            "prompt": f"Professional educational infographic/diagram: {prompt}. High resolution, clean design, academic style, white background, informative. DO NOT include any names like '{self.agent_name}' in the text of the image.",
            "image_size": "landscape_16_9"
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=120)
            
            if response.status_code != 200:
                print(f"⚠️ Primary Modell fehlgeschlagen ({response.status_code}). Nutze Fallback ({self.image_fallback})...")
                url = f"https://fal.run/{self.image_fallback}"
                response = requests.post(url, headers=headers, json=data, timeout=120)

            if response.status_code == 200:
                result = response.json()
                image_url = result.get("images", [{}])[0].get("url")
                if image_url:
                    # Bild herunterladen und lokal speichern
                    img_data = requests.get(image_url).content
                    filename = f"gen_{int(time.time())}.png"
                    local_path = os.path.join(self.gen_images_dir, filename)
                    with open(local_path, "wb") as f:
                        f.write(img_data)
                    print(f"✅ Bild gespeichert: {local_path}")
                    return local_path
            else:
                print(f"⚠️ Fal.ai Fehler ({response.status_code}): {response.text}")
        except Exception as e:
            print(f"⚠️ Fal.ai Fehler: {e}")
        return None

    def build_image_payload(self, image_path, title="Visualisierung"):
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
        payload_path = os.path.join(os.path.dirname(__file__), "payload.html")
        with open(payload_path, "w", encoding="utf-8") as f:
            f.write(html)
        return True

    def search_tavily(self, query):
        print(f"🔍 Agentic Action: Starte Web-Recherche für '{query[:30]}...'")
        url = "https://api.tavily.com/search"
        data = {
            "api_key": self.tavily_key,
            "query": query,
            "search_depth": "basic",
            "include_images": False,
            "max_results": 3
        }
        try:
            resp = requests.post(url, json=data)
            if resp.status_code == 200:
                return resp.json().get("results", [])
        except Exception as e:
            print(f"Tavily Error: {e}")
        return []

    def get_soul(self):
        return self._soul_cache

    def get_user(self):
        return self._user_cache

    def read_transcript(self, transcript_file):
        try:
            with open(transcript_file, "r") as f:
                lines = f.readlines()
                # Nur die letzten 30 Zeilen nehmen, um Tokens zu sparen
                return "".join(lines[-30:])
        except FileNotFoundError:
            return "Noch kein Transkript vorhanden."

    def ask(self, user_query, transcript_file, text_mode=False, action_text=None):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "http://localhost", # Required by OpenRouter
            "X-Title": "Trinity Assistant", # Required by OpenRouter
            "Content-Type": "application/json"
        }
        
        transcript = self.read_transcript(transcript_file)
        soul_prompt = self.get_soul()
        user_prompt = self.get_user()
        
        # Agentic Router
        search_context = ""
        has_payload = False
        
        # action_text = letzten 2-3 Chunks (für präzise Keyword-Erkennung)
        # user_query = voller Kontext (alle 8 Chunks, für LLM-Verständnis)
        router_text = (action_text or user_query).lower()
        lower_query = user_query.lower()
        
        # 1. Timer Agent
        import re
        
        # Konvertiere Zahlwörter zu Digits, da Whisper oft "zwei" statt "2" ausgibt
        num_map = {
            "ein": 1, "eine": 1, "einen": 1, "eins": 1, "zwei": 2, "zwo": 2, 
            "drei": 3, "vier": 4, "fünf": 5, "sechs": 6, "sieben": 7, 
            "acht": 8, "neun": 9, "zehn": 10, "elf": 11, "zwölf": 12,
            "fünfzehn": 15, "zwanzig": 20, "dreißig": 30, "vierzig": 40,
            "fünfzig": 50, "sechzig": 60, "neunzig": 90
        }
        query_digits = router_text
        for word, num in num_map.items():
            query_digits = re.sub(rf'\b{word}\b', str(num), query_digits)
            
        timer_match = re.search(r'timer.*?(\d+)\s*minute', query_digits)
        if timer_match or ("timer" in query_digits and re.search(r'(\d+)', query_digits)):
            # Bevorzuge die Zahl direkt vor 'minute'
            minute_match = re.search(r'(\d+)\s*minute', query_digits)
            if minute_match:
                minutes = int(minute_match.group(1))
            else:
                # Nimm die letzte Zahl im Satz (vermeidet '1' von 'einen Timer')
                numbers = re.findall(r'(\d+)', query_digits)
                if numbers:
                    minutes = int(numbers[-1])
                else:
                    minutes = 1 # Fallback
            
            if minutes > 0:
                html_payload = f"""
                <!-- KEEP_OPEN -->
                <div style="text-align: center; margin-top: 50px;">
                    <div style="font-size: 80px; font-weight: bold; text-shadow: 0 0 20px #00bfff; letter-spacing: 5px;" id="timer">{minutes:02d}:00</div>
                    <div style="font-size: 14px; opacity: 0.5; margin-top: 10px;">Laufender Timer</div>
                </div>
                <script>
                    let time = {minutes * 60};
                    let timerEl = document.getElementById('timer');
                    let interval = setInterval(() => {{
                        time--;
                        if(time <= 0) {{
                            clearInterval(interval);
                            timerEl.innerText = "00:00";
                            timerEl.style.color = "#ff4444";
                            timerEl.style.textShadow = "0 0 20px #ff4444";
                            return;
                        }}
                        let m = Math.floor(time / 60);
                        let s = time % 60;
                        timerEl.innerText = (m < 10 ? "0"+m : m) + ":" + (s < 10 ? "0"+s : s);
                    }}, 1000);
                </script>
                """
                payload_path = os.path.join(os.path.dirname(__file__), "payload.html")
                with open(payload_path, "w", encoding="utf-8") as f:
                    f.write(html_payload)
                has_payload = True
                search_context = f"--- AGENTIC ACTION ---\nDu hast soeben erfolgreich einen visuellen Countdown-Timer auf {minutes} Minuten im UI eingeblendet. Bestätige dem Nutzer kurz und freundlich, dass der Timer jetzt läuft.\n\n"
        
        # 2. Maps Agent
        elif any(word in router_text for word in ["route", "karte", "navigiere", "maps"]):
            # Versuche das Ziel zu finden
            destination = user_query.replace("trinity", "").replace("zeig", "").replace("mir", "").replace("die", "").strip()
            match = re.search(r'(?:nach|zu|in)\s+([A-Za-zäöüÄÖÜß]+)', lower_query)
            if match:
                destination = match.group(1).title()
                
            html_payload = f"""
            <!-- KEEP_OPEN -->
            <h2 style="margin-top: 0; font-weight: 300; border-bottom: 1px solid rgba(255,255,255,0.2); padding-bottom: 10px; font-size: 18px;">Karte: {destination}</h2>
            <div style="width: 100%; height: 320px; border-radius: 15px; overflow: hidden; margin-top: 15px;">
                <iframe 
                    width="100%" 
                    height="100%" 
                    frameborder="0" 
                    style="border:0" 
                    src="https://www.google.com/maps?q={destination}&output=embed" 
                    allowfullscreen>
                </iframe>
            </div>
            """
            payload_path = os.path.join(os.path.dirname(__file__), "payload.html")
            with open(payload_path, "w", encoding="utf-8") as f:
                f.write(html_payload)
            has_payload = True
            search_context = f"--- AGENTIC ACTION ---\nDu hast soeben erfolgreich eine interaktive Google Maps Karte für '{destination}' im UI eingeblendet. Bestätige dem Nutzer kurz, dass die Karte jetzt im Nebenfenster geöffnet ist.\n\n"

        # 3. Simulation Agent
        elif any(word in router_text for word in ["game of life", "simulation", "ameisen", "ant", "raumzeit", "krümmung", "pong"]):
            title = "Simulation"
            sim_script = ""
            desc = ""
            
            if "raumzeit" in lower_query or "krümmung" in lower_query or "gummi" in lower_query:
                title = "Raumzeitkrümmung"
                desc = "Visualisierung einer Gravitationssenke."
                sim_script = """
                const canvas = document.getElementById('simCanvas');
                const ctx = canvas.getContext('2d');
                let time = 0;
                function draw() {
                    ctx.fillStyle = 'rgba(0,0,0,1)';
                    ctx.fillRect(0,0,canvas.width,canvas.height);
                    ctx.strokeStyle = 'rgba(0, 191, 255, 0.4)';
                    ctx.lineWidth = 1;
                    
                    let cx = canvas.width/2;
                    let cy = canvas.height/2 - 50;
                    
                    for(let x=-12; x<=12; x++) {
                        for(let y=-12; y<=12; y++) {
                            let dist = Math.sqrt(x*x + y*y);
                            let depth = 80 / (dist + 1.5); // Gravitationssenke
                            
                            // Isometric projection
                            let isoX = cx + (x - y) * 12;
                            let isoY = cy + (x + y) * 6 + depth + Math.sin(time + dist)*3;
                            
                            if (x < 12) {
                                let ndist = Math.sqrt((x+1)*(x+1) + y*y);
                                let ndepth = 80 / (ndist + 1.5);
                                let nisoX = cx + (x+1 - y) * 12;
                                let nisoY = cy + (x+1 + y) * 6 + ndepth + Math.sin(time + ndist)*3;
                                ctx.beginPath(); ctx.moveTo(isoX, isoY); ctx.lineTo(nisoX, nisoY); ctx.stroke();
                            }
                            if (y < 12) {
                                let ndist = Math.sqrt(x*x + (y+1)*(y+1));
                                let ndepth = 80 / (ndist + 1.5);
                                let nisoX = cx + (x - (y+1)) * 12;
                                let nisoY = cy + (x + (y+1)) * 6 + ndepth + Math.sin(time + ndist)*3;
                                ctx.beginPath(); ctx.moveTo(isoX, isoY); ctx.lineTo(nisoX, nisoY); ctx.stroke();
                            }
                        }
                    }
                    
                    // Masse im Zentrum
                    ctx.beginPath();
                    ctx.arc(cx, cy + 60 + Math.sin(time)*3, 12, 0, Math.PI*2);
                    ctx.fillStyle = '#ff4444';
                    ctx.fill();
                    ctx.shadowBlur = 20;
                    ctx.shadowColor = '#ff4444';
                    ctx.fill();
                    ctx.shadowBlur = 0;
                    
                    time += 0.05;
                    requestAnimationFrame(draw);
                }
                draw();
                """
            elif "ameise" in lower_query or "ant" in lower_query:
                title = "Langton's Ant"
                desc = "Eine zelluläre Ameise, die komplexe Muster webt."
                sim_script = """
                const canvas = document.getElementById('simCanvas');
                const ctx = canvas.getContext('2d');
                const res = 5;
                const cols = canvas.width / res;
                const rows = canvas.height / res;
                let grid = Array(cols).fill().map(() => Array(rows).fill(0));
                let x = Math.floor(cols/2);
                let y = Math.floor(rows/2);
                let dir = 0; // 0=up, 1=right, 2=down, 3=left
                
                ctx.fillStyle = '#000';
                ctx.fillRect(0,0,canvas.width,canvas.height);

                function draw() {
                    for(let n=0; n<50; n++) { // 50 Schritte pro Frame
                        let state = grid[x][y];
                        if (state === 0) {
                            dir = (dir + 1) % 4; // Rechts drehen
                            grid[x][y] = 1;
                            ctx.fillStyle = '#00bfff';
                        } else {
                            dir = (dir + 3) % 4; // Links drehen
                            grid[x][y] = 0;
                            ctx.fillStyle = '#000';
                        }
                        ctx.fillRect(x*res, y*res, res, res);
                        
                        if (dir === 0) y--;
                        else if (dir === 1) x++;
                        else if (dir === 2) y++;
                        else if (dir === 3) x--;
                        
                        if (x < 0) x = cols-1;
                        if (x >= cols) x = 0;
                        if (y < 0) y = rows-1;
                        if (y >= rows) y = 0;
                        
                        ctx.fillStyle = '#ff4444';
                        ctx.fillRect(x*res, y*res, res, res);
                    }
                    requestAnimationFrame(draw);
                }
                draw();
                """
            elif "pong" in lower_query:
                title = "AI Pong Simulation"
                desc = "Zwei einfache Agenten spielen Pong gegeneinander."
                sim_script = """
                const canvas = document.getElementById('simCanvas');
                const ctx = canvas.getContext('2d');
                let ball = {x: 155, y: 155, vx: 4, vy: 3, radius: 5};
                let pad1 = {y: 130, width: 6, height: 50};
                let pad2 = {y: 130, width: 6, height: 50};
                
                function draw() {
                    ctx.fillStyle = '#000';
                    ctx.fillRect(0,0,canvas.width,canvas.height);
                    
                    // Mittellinie
                    ctx.setLineDash([5, 15]);
                    ctx.beginPath(); ctx.moveTo(155, 0); ctx.lineTo(155, 310);
                    ctx.strokeStyle = '#333'; ctx.stroke(); ctx.setLineDash([]);
                    
                    // Physik
                    ball.x += ball.vx;
                    ball.y += ball.vy;
                    if(ball.y <= 0 || ball.y >= 310) ball.vy *= -1;
                    
                    // AI (Paddles folgen dem Ball mit leichter Verzögerung)
                    pad1.y += (ball.y - (pad1.y + 25)) * 0.1;
                    pad2.y += (ball.y - (pad2.y + 25)) * 0.12;
                    
                    // Kollision
                    if(ball.x - ball.radius <= 16 && ball.y >= pad1.y && ball.y <= pad1.y+50) { ball.vx *= -1; ball.x = 16 + ball.radius; }
                    if(ball.x + ball.radius >= 294 && ball.y >= pad2.y && ball.y <= pad2.y+50) { ball.vx *= -1; ball.x = 294 - ball.radius; }
                    
                    // Reset
                    if(ball.x < 0 || ball.x > 310) { ball.x = 155; ball.y = 155; ball.vx *= -1; }
                    
                    // Zeichnen
                    ctx.fillStyle = '#fff';
                    ctx.fillRect(10, pad1.y, pad1.width, pad1.height);
                    ctx.fillRect(294, pad2.y, pad2.width, pad2.height);
                    
                    ctx.beginPath();
                    ctx.arc(ball.x, ball.y, ball.radius, 0, Math.PI*2);
                    ctx.fillStyle = '#00bfff';
                    ctx.fill();
                    
                    requestAnimationFrame(draw);
                }
                draw();
                """
            else:
                title = "Conway's Game of Life"
                desc = "Zellulärer Automat mit simplen Überlebensregeln."
                sim_script = """
                const canvas = document.getElementById('simCanvas');
                const ctx = canvas.getContext('2d');
                const res = 10;
                const cols = canvas.width / res;
                const rows = canvas.height / res;
                let grid = Array(cols).fill().map(() => Array(rows).fill(0).map(() => Math.floor(Math.random() * 2)));

                function draw() {
                    ctx.clearRect(0,0,canvas.width,canvas.height);
                    let next = Array(cols).fill().map(() => Array(rows).fill(0));
                    for(let i=0; i<cols; i++) {
                        for(let j=0; j<rows; j++) {
                            let state = grid[i][j];
                            if (state) {
                                ctx.fillStyle = '#00bfff';
                                ctx.fillRect(i*res, j*res, res-1, res-1);
                            }
                            let sum = 0;
                            for(let x=-1; x<2; x++) {
                                for(let y=-1; y<2; y++) {
                                    let col = (i + x + cols) % cols;
                                    let row = (j + y + rows) % rows;
                                    sum += grid[col][row];
                                }
                            }
                            sum -= state;
                            
                            if (state === 0 && sum === 3) next[i][j] = 1;
                            else if (state === 1 && (sum < 2 || sum > 3)) next[i][j] = 0;
                            else next[i][j] = state;
                        }
                    }
                    grid = next;
                    setTimeout(() => requestAnimationFrame(draw), 80);
                }
                draw();
                """

            html_payload = f"""
            <!-- KEEP_OPEN -->
            <h2 style="margin-top: 0; font-weight: 300; border-bottom: 1px solid rgba(255,255,255,0.2); padding-bottom: 10px; font-size: 18px;">{title}</h2>
            <div style="font-size: 13px; opacity: 0.7; margin-bottom: 10px;">{desc}</div>
            <div style="width: 100%; display: flex; justify-content: center;">
                <canvas id="simCanvas" width="310" height="310" style="background: #000; border-radius: 10px;"></canvas>
            </div>
            <script>
                {sim_script}
            </script>
            """
            payload_path = os.path.join(os.path.dirname(__file__), "payload.html")
            with open(payload_path, "w", encoding="utf-8") as f:
                f.write(html_payload)
            has_payload = True
            search_context = f"--- AGENTIC ACTION ---\nDu hast soeben erfolgreich die JavaScript-Simulation '{title}' im UI gestartet. Bestätige dem Nutzer kurz, dass die Simulation nun im Nebenfenster läuft und erkläre in einem Satz das grundlegende Konzept hinter dieser Simulation.\n\n"

        # 4. Web-Search Agent
        elif any(word in router_text for word in ["recherchier", "such ", "suche ", "finde heraus", "nächste spiel", "nächstes spiel", "spielplan", "nachricht", "online"]):
            # Aktuelles Datum für zeitliche Einordnung
            from datetime import datetime
            now = datetime.now()
            timestamp = now.strftime("%A, %d. %B %Y, %H:%M Uhr")
            date_iso = now.strftime("%Y-%m-%d")
            
            # Aus dem vollen Kontext die eigentliche Suchanfrage extrahieren
            search_query = self.ask_llm([{"role": "user", "content": 
                f"Heute ist {timestamp}.\n"
                f"Der Nutzer hat folgendes gesagt: '{user_query}'\n"
                f"Extrahiere daraus die EINE Suchanfrage für eine Web-Suchmaschine.\n"
                f"Antworte NUR mit dem Suchbegriff (max 8 Wörter, keine Erklärung)."
            }]).strip('" \n.')
            print(f"🔎 Extrahierte Suchanfrage: '{search_query}'")

            if len(search_query) < 3:
                search_context = "--- AGENTIC ACTION ---\nDie Suchanfrage war unklar. Bitte den Nutzer, das Thema genauer zu benennen.\n\n"
            else:
                results = self.search_tavily(search_query)
                if results:
                    print(f"✅ Tavily: {len(results)} Ergebnisse gefunden")
                    search_results_text = "\n".join([f"- {r['title']}: {r['content']}" for r in results])
                    search_context = (
                        f"--- AKTUELLE WEB-RECHERCHE (ECHTZEIT-DATEN) ---\n"
                        f"HEUTIGES DATUM: {timestamp} (ISO: {date_iso})\n"
                        f"Suchanfrage: '{search_query}'\n"
                        f"Die Web-Suche lieferte folgende frische Fakten. Diese sind aktueller als dein Training. "
                        f"Nutze AUSSCHLIESSLICH diese Daten – ignoriere dein internes Wissen zu diesem Thema. "
                        f"Beachte das heutige Datum, um korrekt zu bestimmen, welche Ereignisse in der Zukunft liegen:\n"
                        f"{search_results_text}\n\n"
                    )
                    
                    # Payload für das UI-Dashboard erstellen (Absätze statt Listen)
                    html_items = "".join([f"<div style='margin-bottom:20px;'><a href='{r.get('url','')}' style='color:#00bfff; font-weight:bold;'>{r['title']}</a><div style='font-size:15px; opacity:0.9; margin-top:5px; line-height:1.4;'>{r['content']}</div></div>" for r in results])
                    html_payload = f"<h2 style='margin-top: 0; font-weight: 300; border-bottom: 1px solid rgba(255,255,255,0.2); padding-bottom: 10px; font-size: 18px;'>🔍 {search_query}</h2><div style='padding-top:10px;'>{html_items}</div>"
                    
                    payload_path = os.path.join(os.path.dirname(__file__), "payload.html")
                    with open(payload_path, "w", encoding="utf-8") as f:
                        f.write(html_payload)
                    has_payload = True
                else:
                    search_context = "--- AGENTIC ACTION ---\nDie Web-Suche ergab keine Ergebnisse. Informiere den Nutzer darüber und biete an, mit anderen Begriffen zu suchen.\n\n"

        
        # 5. Bildgenerierung / Visualisierung (Direkt via Fal.ai)
        # SICHERHEITS-CHECK: Bild nur generieren, wenn explizit gefordert (nicht nur Wort "Bild" erwähnen)
        # Und die Query muss eine gewisse Mindestlänge haben, um "Quark" zu vermeiden
        elif any(word in router_text for word in ["infografik", "grafik", "visualisier", "schaubild", "illustration"]) or \
             (any(word in router_text for word in ["bild", "zeichnung"]) and any(cmd in router_text for cmd in ["erstell", "mach", "generier", "zeig"])):
            
            if len(user_query) < 15:
                print(f"⚠️ Bild-Trigger ignoriert: Query zu kurz ({len(user_query)} Zeichen).")
                search_context = ""
            else:
                print(f"🚀 Starte Bildgenerierung für: '{user_query[:50]}'")
            
            # Aus dem vollen Kontext das Bildthema extrahieren
            prompt = self.ask_llm([{"role": "user", "content": 
                f"Der Nutzer hat folgendes gesagt: '{user_query}'\n"
                f"Extrahiere daraus das THEMA für ein Schaubild/Infografik.\n"
                f"Antworte NUR mit dem Thema (max 10 Wörter, keine Erklärung, kein Name wie 'Trinity')."
            }]).strip('" \n.')
            print(f"🎨 Extrahiertes Bildthema: '{prompt}'")
            
            if len(prompt) < 3:
                prompt = user_query[:80]  # Fallback
            
            img_path = self.generate_image_fal(prompt)
            if img_path:
                has_payload = self.build_image_payload(img_path, title=prompt.title())
                search_context = f"--- IMAGE GENERATION ---\nDu hast soeben ein Schaubild zu '{prompt}' generiert. Bestätige dem Nutzer, dass er das Bild nun im Nebenfenster sehen kann und biete an, Details dazu zu erklären.\n\n"
            else:
                search_context = "--- FEHLER ---\nDie Bildgenerierung ist fehlgeschlagen. Bitte entschuldige dich beim Nutzer.\n\n"

        # 6. Aktienkurs-Agent
        elif any(word in router_text for word in ["aktienkurs", "aktie", "kurs von", "preis von", "stock", "krypto", "bitcoin", "ethereum"]):
            # Ticker-Symbol extrahieren
            ticker_match = re.search(r'\b([A-Z]{2,5})\b', user_query)
            # Versuche auch geschriebene Namen zu erkennen
            known_tickers = {
                "apple": "AAPL", "microsoft": "MSFT", "google": "GOOGL", "alphabet": "GOOGL",
                "amazon": "AMZN", "tesla": "TSLA", "nvidia": "NVDA", "meta": "META",
                "netflix": "NFLX", "sap": "SAP", "siemens": "SIE.DE", "volkswagen": "VOW3.DE",
                "bmw": "BMW.DE", "bayer": "BAYN.DE", "bitcoin": "BTC-USD", "ethereum": "ETH-USD"
            }
            ticker = None
            for name, sym in known_tickers.items():
                if name in lower_query:
                    ticker = sym
                    break
            if not ticker and ticker_match:
                ticker = ticker_match.group(1)

            if ticker:
                try:
                    quote_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=5d"
                    resp = requests.get(quote_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
                    if resp.status_code == 200:
                        data = resp.json()
                        meta = data["chart"]["result"][0]["meta"]
                        price = meta.get("regularMarketPrice", 0)
                        prev_close = meta.get("chartPreviousClose", meta.get("previousClose", price))
                        currency = meta.get("currency", "")
                        change = price - prev_close
                        change_pct = (change / prev_close * 100) if prev_close else 0
                        color = "#00ff88" if change >= 0 else "#ff4444"
                        arrow = "▲" if change >= 0 else "▼"
                        name_display = meta.get("shortName", ticker)

                        # Historische Punkte für Mini-Chart
                        closes = data["chart"]["result"][0]["indicators"]["quote"][0].get("close", [])
                        closes = [c for c in closes if c is not None][-5:]
                        min_p = min(closes) if closes else price
                        max_p = max(closes) if closes else price
                        points_count = len(closes)
                        svg_width = 280
                        svg_height = 60
                        if points_count > 1 and max_p != min_p:
                            pts = " ".join([
                                f"{int(i * svg_width / (points_count-1))},{int(svg_height - (c - min_p) / (max_p - min_p) * svg_height)}"
                                for i, c in enumerate(closes)
                            ])
                            sparkline = f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"/>'
                        else:
                            sparkline = f'<line x1="0" y1="30" x2="{svg_width}" y2="30" stroke="{color}" stroke-width="2"/>'

                        html_payload = f"""
<h2 style='margin-top:0;font-weight:300;border-bottom:1px solid rgba(255,255,255,0.2);padding-bottom:10px;font-size:18px;'>📈 {name_display}</h2>
<div style='text-align:center;padding:15px 0;'>
  <div style='font-size:48px;font-weight:bold;color:{color};text-shadow:0 0 20px {color};'>{price:.2f} <span style='font-size:20px;'>{currency}</span></div>
  <div style='font-size:18px;color:{color};margin-top:5px;'>{arrow} {change:+.2f} ({change_pct:+.2f}%)</div>
  <div style='font-size:12px;opacity:0.5;margin-top:5px;'>Vortag: {prev_close:.2f} {currency}</div>
</div>
<svg width='{svg_width}' height='{svg_height}' style='display:block;margin:0 auto;opacity:0.8;'>{sparkline}</svg>
<div style='font-size:11px;opacity:0.4;text-align:center;margin-top:8px;'>5-Tage Verlauf · Yahoo Finance</div>"""
                        payload_path = os.path.join(os.path.dirname(__file__), "payload.html")
                        with open(payload_path, "w", encoding="utf-8") as f:
                            f.write(html_payload)
                        has_payload = True
                        search_context = (
                            f"--- AGENTIC ACTION: ABGESCHLOSSEN ---\n"
                            f"Du hast den Kurs von {name_display} ({ticker}) live abgerufen: "
                            f"{price:.2f} {currency} ({arrow} {change_pct:+.2f}% heute). "
                            f"Das interaktive Chart ist BEREITS im Nebenfenster sichtbar.\n"
                            f"DEINE AUFGABE JETZT: Sag NUR einen einzigen kurzen Satz auf Deutsch, der den Kurs bestätigt. "
                            f"Beispiel: 'Nvidia steht gerade bei 950 Dollar, heute plus zwei Prozent.'\n"
                            f"VERBOTEN: CSV, Tabellen, Listen, Markdown, erklärende Sätze, Quellenangaben.\n\n"
                        )
                except Exception as e:
                    print(f"⚠️ Aktienkurs Fehler: {e}")

        # 7. Zusammenfassung der Sitzung (Big Picture) - Lokal via LLM
        elif any(phrase in router_text for phrase in [
            "big picture", "big-picture", "überblick der vorlesung", "überblick der sitzung",
            "zusammenfassung der vorlesung", "zusammenfassung der heutigen",
            "infografik der vorlesung", "infografik der sitzung",
            "visualisiere die vorlesung"
        ]):
            print(f"📊 Erstelle Zusammenfassung der Sitzung...")
            transcript = self.read_transcript(transcript_file)
            
            prompt = (
                f"Fasse die bisherige Vorlesungssitzung basierend auf diesem Transkript zusammen:\n"
                f"{transcript[:3000]}\n\n"
                f"Antworte auf Deutsch, strukturiert mit Bullet-Points."
            )
            summary = self.ask_llm([{"role": "user", "content": prompt}])
            
            if summary:
                # Absätze statt simpler Zeilenumbrüche für mehr Luftigkeit
                paragraphs = [p.strip() for p in summary.split('\n') if p.strip()]
                formatted_summary = "".join([f"<p style='margin-bottom:15px; line-height:1.5;'>{p}</p>" for p in paragraphs])
                html_payload = f"<!-- KEEP_OPEN --><h2>📊 Sitzungs-Überblick</h2><div style='font-size:15px; opacity:0.9;'>{formatted_summary}</div>"
                payload_path = os.path.join(os.path.dirname(__file__), "payload.html")
                with open(payload_path, "w", encoding="utf-8") as f:
                    f.write(html_payload)
                has_payload = True
                search_context = "--- SUMMARY ---\nDu hast eine Zusammenfassung der Sitzung erstellt. Erkläre dem Nutzer kurz die wichtigsten Punkte.\n\n"

        # RAG: Nur bei explizitem Nachschlag-Trigger
        rag_context = ""
        # Wir unterdrücken RAG, wenn bereits eine Web-Suche aktiv ist, außer es wird explizit "Skript" oder "Buch" erwähnt
        is_web_search_active = (search_context != "")
        
        # RAG nur bei SEHR expliziten Skript/Buch-Bezügen – niemals bei allgemeinen Anfragen
        rag_triggers = ["laut skript", "im skript", "im buch", "laut buch",
                        "wissensbasis", "rag", "schlag nach", "nachschlagen"]
        
        should_trigger_rag = any(t in lower_query for t in rag_triggers)
        
        # Web-Suche hat immer Vorrang – niemals beides gleichzeitig
        if is_web_search_active:
            should_trigger_rag = False

        if should_trigger_rag:
            print("📚 RAG-Suche aktiviert...")
            rag_result = self.retrieve_rag(user_query)
            if rag_result:
                rag_context = (
                    f"--- RELEVANTE LEHRINHALTE (aus deiner Wissensbasis) ---\n"
                    f"Nutze folgende Auszüge aus den Vorlesungsskripten/Büchern, "
                    f"um fachlich korrekt zu antworten:\n\n{rag_result}\n\n"
                )

        context_prompt = (
            f"{soul_prompt}\n\n"
            f"--- INFORMATIONEN ZUM NUTZER UND ZIELPUBLIKUM ---\n"
            f"{user_prompt}\n\n"
            f"{search_context}"
            f"{rag_context}"
            f"--- AKTUELLES VORLESUNGS-TRANSKRIPT ---\n"
            f"Hier ist das aktuelle Transkript der Vorlesung inklusive Zeitstempel:\n"
            f"{transcript}\n\n"
            f"Regel: Wenn du nach dem Transkript oder vergangenen Aussagen gefragt wirst, "
            f"beziehe dich exakt auf die Informationen und Zeitstempel in diesem Transkript."
        )

        data = {
            "model": self.model,
            "temperature": 0.1,
            "max_tokens": 250,   # Kurze Sprachantworten – größter Latenzgewinn
            "messages": [
                {"role": "system", "content": context_prompt},
                {"role": "user", "content": user_query}
            ]
        }
        
        try:
            print(f"🧠 Trinity denkt nach über: '{user_query}'...")
            response = requests.post(self.url, headers=headers, json=data)
            response.raise_for_status()
            
            result = response.json()
            msg = result['choices'][0]['message']
            # Qwen3-Fix: Im Thinking-Modus ist 'content' leer, Antwort steht in 'reasoning_content'
            answer = (msg.get('content') or msg.get('reasoning_content') or '').strip()
            print(f"💡 Antwort ({len(answer)} Zeichen): {answer[:80]}...")
            
            # Falls Textmodus aktiv ist und noch kein Payload gesetzt wurde (z.B. keine Map), erzeuge Untertitel-Payload
            if text_mode and not has_payload:
                formatted_answer = answer.replace('\n', '<br>')
                # Ohne KEEP_OPEN, damit es automatisch schließt, wenn sie aufhört zu sprechen
                html_payload = f"""
                <h2 style="margin-top: 0; font-weight: 300; border-bottom: 1px solid rgba(255,255,255,0.2); padding-bottom: 10px; font-size: 18px;">Antwort</h2>
                <div style="font-size: 16px; line-height: 1.5; opacity: 0.9;">
                    {formatted_answer}
                </div>
                """
                payload_path = os.path.join(os.path.dirname(__file__), "payload.html")
                with open(payload_path, "w", encoding="utf-8") as f:
                    f.write(html_payload)
                has_payload = True

            return answer, has_payload
            
        except Exception as e:
            print(f"Fehler bei der Kommunikation mit dem Gehirn: {e}")
            return "Entschuldigung, ich habe gerade den Faden verloren. Bitte wiederhole das.", False

if __name__ == "__main__":
    # Kalttest-Skript
    brain = TrinityBrain()
    antwort, _ = brain.ask("Erkläre in einem Satz, was ein autonomer Agent ist.", "memory/test.md")
    print(f"Antwort: {antwort}")

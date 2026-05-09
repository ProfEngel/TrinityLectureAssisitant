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
        
        self.load_config()
        
        self.live_skills = []
        self._load_live_skills()

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
            
            apis = config.get("apis", {})
            self.tavily_key = apis.get("tavily", "")
            self.fal_key = apis.get("fal_ai", "")
            
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

    def _load_live_skills(self):
        """Lädt alle Live-Skills aus dem agents/ Ordner dynamisch beim Start."""
        import importlib.util
        agents_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "agents")
        if not os.path.exists(agents_dir):
            return
            
        for item in os.listdir(agents_dir):
            skill_dir = os.path.join(agents_dir, item)
            script_path = os.path.join(skill_dir, "script.py")
            if os.path.isdir(skill_dir) and os.path.exists(script_path):
                try:
                    spec = importlib.util.spec_from_file_location(f"agents.{item}", script_path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    if hasattr(module, "can_handle") and hasattr(module, "execute"):
                        self.live_skills.append(module)
                        print(f"🔌 Live-Skill geladen: {item}")
                except Exception as e:
                    print(f"⚠️ Fehler beim Laden des Skills {item}: {e}")

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
        
        # --- DYNAMIC SKILL DISPATCH ---
        skill_handled = False
        for skill in getattr(self, 'live_skills', []):
            if skill.can_handle(router_text):
                try:
                    result = skill.execute(router_text, context={"brain": self})
                    if result.get("has_payload"):
                        payload_path = os.path.join(os.path.dirname(__file__), "payload.html")
                        with open(payload_path, "w", encoding="utf-8") as f:
                            f.write(result.get("html_payload", ""))
                        has_payload = True
                        search_context = result.get("search_context", "")
                    skill_handled = True
                    break
                except Exception as e:
                    print(f"⚠️ Fehler bei der Skill-Ausführung: {e}")
        

        # Die RAG Logik wurde in den rag_agent ausgelagert.
        # Er gibt den 'search_context' über die Live-Skills Pipeline zurück.
        rag_context = search_context

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

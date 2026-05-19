from faster_whisper import WhisperModel
import sounddevice as sd
import numpy as np
import os
os.environ["OMP_NUM_THREADS"] = "8"
os.environ["KMP_BLOCKTIME"] = "1"
import time
import queue
import sys
import re
import subprocess
import threading
import warnings

# Warnings unterdrücken (faster-whisper matmul + urllib3 SSL)
warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", message=".*NotOpenSSLWarning.*")
warnings.filterwarnings("ignore", message=".*urllib3.*")
# Damit der Import aus dem gleichen Verzeichnis funktioniert
sys.path.append(os.path.dirname(__file__))
from brain import TrinityBrain

# Konfiguration
MODEL = "small"  # Schnell auf CPU: <1s Latenz. Für beste Qualität: 'large-v3-turbo'
SAMPLE_RATE = 16000
CHUNK_DURATION = 2
TRIGGER_WORD = "Trinity"
CORE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(CORE_DIR)
MEMORY_DIR = os.path.join(PROJECT_DIR, "memory")
os.makedirs(MEMORY_DIR, exist_ok=True)
SILENCE_THRESHOLD = 0.05
INITIAL_PROMPT = "Trinity, Spieltheorie, Vorlesung, Informatik, ERP, Nash-Gleichgewicht, Hebbsche Regel, Infografik."

# Fuzzy Wake-Word Varianten (Fallback, wird aus config.json überschrieben)
TRIGGER_VARIANTS = ["trinity", "triniti", "trindy", "trinnity", "trinitiy", "trenty", "trendy"]

def has_trigger(text, variants=None):
    """Prüft ob das Wake-Word (oder eine Variante) im Text vorkommt."""
    lower = text.lower()
    check_list = variants or TRIGGER_VARIANTS
    return any(v in lower for v in check_list)

def set_state(state):
    state_file = os.path.join(CORE_DIR, "state.txt")
    try:
        with open(state_file, "w") as f:
            f.write(state)
    except:
        pass

class MorpheusEar:
    def __init__(self):
        # Konfiguration laden
        self.brain = TrinityBrain()
        self.config_path = os.path.join(CORE_DIR, "config.json")
        self.load_config()

        self.audio_queue = queue.Queue()
        self.is_running = False
        self.speak_process = None
        self.recent_chunks = []  # Kontext-Ringpuffer (letzten N Chunks)
        self.is_muted = False  # Stumm-Modus: Trinity hört nicht zu
        self.trigger_armed = False # Wartet auf Ende des Satzes nach Wake-Word
        
        # Neues Transkript für diese Sitzung anlegen
        timestamp = time.strftime("%d%b%Y_%H%M")
        self.transcript_file = os.path.join(MEMORY_DIR, f"raw_session_{timestamp}.md")
        with open(self.transcript_file, "w") as f:
            f.write(f"# Trinity Session Log - {timestamp}\n\n")
            
        print(f"Lade Whisper Modell ({self.model_name}) via faster-whisper...")
        # int8 = quantisiert, cpu = Apple Silicon kompatibel, download_root cached das Modell
        self._whisper = WhisperModel(self.model_name, device="cpu", compute_type="int8", cpu_threads=8)
        print("✅ Whisper Modell geladen.")

    def load_config(self):
        """Lädt STT-spezifische Settings aus der config.json."""
        try:
            import json
            with open(self.config_path, "r") as f:
                config = json.load(f)
            self.model_name = config["stt"]["model"]
            self.silence_threshold = config["stt"]["silence_threshold"]
            self.chunk_duration = config["stt"]["chunk_duration"]
            self.show_volume_meter = config["stt"].get("show_volume_meter", False)
            self.voice = config["tts"]["voice"]
            # Persona-Config laden
            persona = config.get("persona", {})
            self.agent_name = persona.get("agent_name", TRIGGER_WORD)
            self.trigger_variants = persona.get("trigger_variants", TRIGGER_VARIANTS)
            
            # Proactive-Config
            self.proactive_cfg = config.get("proactive", {})
            # Audio-Routing Config
            self.audio_routing = config.get("audio_routing", {})
            # Telegram Config
            self.telegram_cfg = config.get("telegram", {})
            # System Config
            self.system_cfg = config.get("system", {})
            self.mode = self.system_cfg.get("mode", "office")
        except:
            self.model_name = MODEL
            self.silence_threshold = SILENCE_THRESHOLD
            self.chunk_duration = CHUNK_DURATION
            self.show_volume_meter = False
            self.voice = "Samantha"
            self.agent_name = TRIGGER_WORD
            self.trigger_variants = TRIGGER_VARIANTS
            self.proactive_cfg = {}
            self.audio_routing = {}
            self.telegram_cfg = {}
            self.system_cfg = {}
            self.mode = "office"

    def _heartbeat_loop(self):
        interval_min = self.proactive_cfg.get("interval_minutes", 2)
        print(f"💓 Heartbeat aktiv (Intervall: {interval_min} Min).")
        while self.is_running:
            time.sleep(interval_min * 60)
            # Abbrechen wenn gestoppt, Heartbeat deaktiviert oder Chat-Modus aktiv
            if (not self.is_running
                    or not self.proactive_cfg.get("heartbeat_enabled", False)
                    or getattr(self, 'mode', 'office') == 'chat'):
                break
                
            try:
                # Transkript auslesen (die letzten ca. 3000 Zeichen sollten für 2 Min reichen)
                with open(self.transcript_file, "r") as f:
                    content = f.read()
                recent_text = content[-3000:] if len(content) > 3000 else content
                
                # Check ob wir überhaupt Content haben
                if len(recent_text.strip()) < 100:
                    continue
                    
                print("💓 Heartbeat: Analysiere Transkript im Hintergrund...")
                
                sys.path.append(os.path.join(PROJECT_DIR, "agents"))
                import importlib
                hb_module = importlib.import_module("heartbeat_agent.script")
                
                result = hb_module.analyze_transcript(self.brain, recent_text)
                if result and result.get("has_finding"):
                    color = result.get("bubble_color", "red")
                    msg = result.get("message", "Heartbeat Hinweis.")
                    print(f"💓 Heartbeat Finding ({color}): {msg}")
                    
                    # Schreibe Payload
                    payload_path = os.path.join(CORE_DIR, "bubble_payload.html")
                    if color == "blue":
                        title = "📘 Übungsaufgabe"
                        task_text = result.get("task", "")
                        solution_text = result.get("solution", "")
                        html = f"<!-- KEEP_OPEN --><h2 style='margin-top:0;font-weight:300;border-bottom:1px solid rgba(255,255,255,0.2);padding-bottom:10px;font-size:18px;'>{title}</h2><p style='font-size:16px; line-height: 1.5;'>{task_text}</p><div style='height: 500px; display: flex; align-items:flex-end; justify-content:center; opacity:0.5;'>Scroll runter für die Lösung 👇</div><div style='padding-top: 50px; border-top: 1px solid rgba(255,255,255,0.2);'><strong style='color:#00e5ff;'>Lösung:</strong><p style='font-size:16px; line-height: 1.5;'>{solution_text}</p></div>"
                        msg_log = f"{task_text} (Lösung: {solution_text})"
                    else:
                        title = "⚠️ Fehler erkannt" if color == "red" else ("💡 Alternative Perspektive" if color == "yellow" else "ℹ️ Info")
                        html = f"<!-- KEEP_OPEN --><h2 style='margin-top:0;font-weight:300;border-bottom:1px solid rgba(255,255,255,0.2);padding-bottom:10px;font-size:18px;'>{title}</h2><p style='font-size:16px; line-height: 1.5;'>{msg}</p>"
                        msg_log = msg

                    # Füge Separator hinzu, falls es schon andere Bubbles gibt (Akkumulation)
                    separator = "<hr style='border:none; border-top:1px dashed rgba(255,255,255,0.3); margin:20px 0;'>" if os.path.exists(payload_path) else ""

                    with open(payload_path, "a") as f:
                        f.write(separator + html)
                        
                    # State auf bubble_* setzen (damit Trinity_App es zeichnet)
                    set_state(f"bubble_{color}")
                    
                    # 📝 Heartbeat Findings direkt ins Transkript schreiben für Langzeitgedächtnis und Summary!
                    with open(self.transcript_file, "a", encoding="utf-8") as f:
                        t_stamp = time.strftime("%H:%M:%S")
                        f.write(f"[{t_stamp}] [Heartbeat-Analyse ({title})]: {msg_log}\n")
                        
                    # 📱 Telegram Bridge (falls aktiv)
                    if self.telegram_cfg.get("enabled", False) and self.telegram_cfg.get("bot_token") and self.telegram_cfg.get("chat_id"):
                        try:
                            import requests
                            tg_url = f"https://api.telegram.org/bot{self.telegram_cfg['bot_token']}/sendMessage"
                            tg_msg = f"*{title}*\n{msg}"
                            requests.post(tg_url, json={
                                "chat_id": self.telegram_cfg["chat_id"],
                                "text": tg_msg,
                                "parse_mode": "Markdown"
                            }, timeout=5)
                        except Exception as tg_ex:
                            print(f"⚠️ Telegram Sende-Fehler: {tg_ex}")
            except Exception as e:
                print(f"⚠️ Heartbeat Error: {e}")
                
    def _telegram_listener_loop(self):
        """Hintergrund-Thread für den Empfang von Telegram-Nachrichten (Two-Way Bridge)."""
        print("📱 Telegram Listener Thread gestartet.")
        last_update_id = 0
        import requests
        
        while self.is_running:
            try:
                url = f"https://api.telegram.org/bot{self.telegram_cfg['bot_token']}/getUpdates"
                params = {"offset": last_update_id, "timeout": 10}
                resp = requests.get(url, params=params, timeout=15)
                
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("ok"):
                        for result in data.get("result", []):
                            update_id = result.get("update_id")
                            last_update_id = update_id + 1
                            
                            message = result.get("message", {})
                            text = message.get("text", "")
                            voice = message.get("voice", {})
                            chat_id = message.get("chat", {}).get("id")
                            
                            # Nur Nachrichten vom authorisierten Admin-Chat akzeptieren
                            if str(chat_id) == str(self.telegram_cfg.get("chat_id")):
                                if text:
                                    print(f"📥 Telegram Nachricht empfangen: {text}")
                                    
                                    # Ins Session-Log schreiben
                                    t_stamp = time.strftime("%H:%M:%S")
                                    with open(self.transcript_file, "a", encoding="utf-8") as f:
                                        f.write(f"[{t_stamp}] [User (via Telegram)]: {text}\n")
                                    
                                    # Trinity triggern, als wäre es gesprochen worden
                                    trigger_text = f"{self.agent_name}, {text}"
                                    self.trigger_action(trigger_text, silent_response=False, from_telegram=True)
                                
                                elif message.get("photo"):
                                    # 📸 Foto empfangen → I2I-Workflow auslösen
                                    caption = message.get("caption", "").strip()
                                    print(f"📸 Telegram Foto empfangen. Caption: '{caption}'")
                                    threading.Thread(
                                        target=self._handle_telegram_photo,
                                        args=(message, caption),
                                        daemon=True
                                    ).start()

                                elif voice:
                                    print("📥 Telegram Sprachnachricht empfangen. Lade herunter...")
                                    tg_token = self.telegram_cfg['bot_token']
                                    tg_chat = self.telegram_cfg['chat_id']
                                    try:
                                        file_id = voice.get("file_id")
                                        file_info = requests.get(f"https://api.telegram.org/bot{tg_token}/getFile?file_id={file_id}").json()
                                        if file_info.get("ok"):
                                            file_path = file_info["result"]["file_path"]
                                            audio_url = f"https://api.telegram.org/file/bot{tg_token}/{file_path}"
                                            audio_data = requests.get(audio_url).content
                                            tmp_file = "/tmp/tg_voice.oga"
                                            with open(tmp_file, "wb") as f:
                                                f.write(audio_data)
                                                
                                            print("🎙️ Transkribiere Telegram Sprachnachricht...")
                                            segments, _ = self._whisper.transcribe(tmp_file, language="de")
                                            voice_text = " ".join([segment.text for segment in segments]).strip()
                                            
                                            if voice_text:
                                                print(f"📥 Telegram Sprachnachricht (transkribiert): {voice_text}")
                                                
                                                # Bestätigungs-Echo: User weiß, was transkribiert wurde
                                                requests.post(
                                                    f"https://api.telegram.org/bot{tg_token}/sendMessage",
                                                    json={"chat_id": tg_chat, "text": f"🎙️ Ich habe verstanden:\n_{voice_text}_", "parse_mode": "Markdown"},
                                                    timeout=5
                                                )
                                                
                                                # Ins Session-Log schreiben
                                                t_stamp = time.strftime("%H:%M:%S")
                                                with open(self.transcript_file, "a", encoding="utf-8") as f:
                                                    f.write(f"[{t_stamp}] [User (via Telegram Voice)]: {voice_text}\n")
                                                
                                                # Trinity triggern, als wäre es gesprochen worden
                                                trigger_text = f"{self.agent_name}, {voice_text}"
                                                self.trigger_action(trigger_text, silent_response=False, from_telegram=True)
                                    except Exception as ex:
                                        print(f"⚠️ Fehler bei der Verarbeitung der Sprachnachricht: {ex}")
                                        # Bug Fix: Fehler-Feedback an User senden
                                        try:
                                            requests.post(
                                                f"https://api.telegram.org/bot{tg_token}/sendMessage",
                                                json={"chat_id": tg_chat, "text": f"❌ Sprachnachricht konnte nicht verarbeitet werden: {ex}"},
                                                timeout=5
                                            )
                                        except Exception:
                                            pass
            except Exception as e:
                pass
            time.sleep(2)
        

    def _handle_telegram_photo(self, message: dict, caption: str):
        """
        Verarbeitet ein empfangenes Telegram-Foto:
        1. Lädt das Bild herunter → media/input/
        2. Ruft execute_i2i() im comfyui_agent auf
        3. Ergebnis geht automatisch zurück an Telegram (innerhalb von execute_i2i)
        """
        import requests as req
        tg_token = self.telegram_cfg.get("bot_token", "")
        chat_id = self.telegram_cfg.get("chat_id", "")

        try:
            # Bestes (größtes) Foto aus der Liste nehmen
            photos = message.get("photo", [])
            if not photos:
                return
            best_photo = max(photos, key=lambda p: p.get("file_size", 0))
            file_id = best_photo.get("file_id")

            # Datei-Pfad vom Telegram-Server abfragen
            file_info = req.get(
                f"https://api.telegram.org/bot{tg_token}/getFile?file_id={file_id}",
                timeout=10
            ).json()
            if not file_info.get("ok"):
                print("⚠️ Konnte Telegram-Foto-Info nicht abrufen.")
                return

            file_path = file_info["result"]["file_path"]
            file_ext = os.path.splitext(file_path)[1] or ".jpg"
            img_data = req.get(
                f"https://api.telegram.org/file/bot{tg_token}/{file_path}",
                timeout=30
            ).content

            # Lokal in media/input/ speichern
            comfyui_agent_dir = os.path.join(
                PROJECT_DIR, "agents", "comfyui_agent", "media", "input"
            )
            os.makedirs(comfyui_agent_dir, exist_ok=True)
            local_filename = f"tg_upload_{int(time.time())}{file_ext}"
            local_path = os.path.join(comfyui_agent_dir, local_filename)
            with open(local_path, "wb") as f:
                f.write(img_data)
            print(f"📥 Telegram-Foto gespeichert: {local_path}")

            # Im Brain merken für Folgeanweisungen
            self.brain.last_media_path = local_path

            # Nutzer-Bestätigung senden
            req.post(
                f"https://api.telegram.org/bot{tg_token}/sendMessage",
                json={"chat_id": chat_id,
                      "text": f"🖼️ Bild empfangen. Starte ComfyUI I2I...\nPrompt: '{caption or 'kein Prompt'}'"},
                timeout=5
            )

            # comfyui_agent laden
            import importlib.util
            script_path = os.path.join(PROJECT_DIR, "agents", "comfyui_agent", "script.py")
            spec = importlib.util.spec_from_file_location("comfyui_agent", script_path)
            comfyui_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(comfyui_mod)

            context = {
                "brain": self.brain,
                "from_telegram": True,
                "telegram_cfg": self.telegram_cfg,
            }

            # Routing: Video-Keywords in Caption → I2V, sonst → I2I
            is_video_request = (
                hasattr(comfyui_mod, "can_handle_video") and
                comfyui_mod.can_handle_video(caption or "")
            )

            if is_video_request:
                # --- I2V: Image → Kurzvideo via LTX 2.3 ---
                req.post(
                    f"https://api.telegram.org/bot{tg_token}/sendMessage",
                    json={"chat_id": chat_id,
                          "text": f"🎬 Bild empfangen. Starte LTX 2.3 I2V...\nPrompt: '{caption or 'kein Prompt'}'"},
                    timeout=5
                )
                result = comfyui_mod.execute_i2v(
                    query=caption or "smooth cinematic motion",
                    input_image_path=local_path,
                    context=context
                )
                log_mode = "I2V"
                log_response = "Video generiert und zurückgesendet."
            else:
                # --- I2I: Image → Bild via Flux2 ---
                req.post(
                    f"https://api.telegram.org/bot{tg_token}/sendMessage",
                    json={"chat_id": chat_id,
                          "text": f"🖼️ Bild empfangen. Starte ComfyUI I2I...\nPrompt: '{caption or 'kein Prompt'}'"},
                    timeout=5
                )
                result = comfyui_mod.execute_i2i(
                    query=caption or "transform this image",
                    input_image_path=local_path,
                    context=context
                )
                log_mode = "I2I"
                log_response = "Bild generiert und zurückgesendet."

            # Falls UI-Payload vorhanden, anzeigen
            if result.get("has_payload") and result.get("html_payload"):
                payload_path = os.path.join(CORE_DIR, "payload.html")
                with open(payload_path, "w", encoding="utf-8") as f:
                    f.write(result["html_payload"])
                set_state("reporting")

            # Log
            t_stamp = time.strftime("%H:%M:%S")
            with open(self.transcript_file, "a", encoding="utf-8") as f:
                f.write(f"[{t_stamp}] [User (Telegram {log_mode})]: Foto hochgeladen, Prompt: '{caption}'\n")
                f.write(f"[{t_stamp}] [Trinity (ComfyUI {log_mode})]: {log_response}\n")

        except Exception as e:
            print(f"⚠️ Fehler beim Verarbeiten des Telegram-Fotos: {e}")
            try:
                req.post(
                    f"https://api.telegram.org/bot{tg_token}/sendMessage",
                    json={"chat_id": chat_id, "text": f"❌ Fehler bei der Verarbeitung: {e}"},
                    timeout=5
                )
            except Exception:
                pass


    def audio_callback(self, indata, frames, time, status):

        """Wird vom sounddevice Stream aufgerufen."""
        if status:
            print(f"Audio Error: {status}")
        # Wir sammeln IMMER Audio, auch wenn sie spricht, um Unterbrechungen zu ermöglichen
        self.audio_queue.put(indata.copy())

    def start(self):
        self.is_running = True
        set_state("idle")
        
        # Start Heartbeat Thread only if enabled AND not in chat mode
        if self.proactive_cfg.get("heartbeat_enabled", False) and self.mode != "chat":
            threading.Thread(target=self._heartbeat_loop, daemon=True).start()
            
        # Start Telegram Listener Thread if enabled
        if self.telegram_cfg.get("enabled", False) and self.telegram_cfg.get("bot_token"):
            threading.Thread(target=self._telegram_listener_loop, daemon=True).start()
        
        cmd_file = os.path.join(os.path.dirname(__file__), "cmd.txt")
        
        # Wir lesen in kleineren Häppchen (0.5s), um stabiler zu sein
        block_size = int(SAMPLE_RATE * 0.5)
        blocks_per_chunk = int(self.chunk_duration / 0.5)
        
        self.audio_stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, callback=self.audio_callback, blocksize=block_size)
        
        if self.mode != "chat":
            self.audio_stream.start()
            print(f"Trinity hört jetzt zu... (Model: {self.model_name}, Thresh: {self.silence_threshold})")
        else:
            print("💬 Chat-Modus aktiv: STT und Mikrofon bleiben deaktiviert. Höre nur auf UI (Flüstern) oder Telegram.")
            
        audio_buffer = []
        try:
            while self.is_running:
                # 1. Prüfe auf stille Text-Eingaben
                if os.path.exists(cmd_file):
                    try:
                        with open(cmd_file, "r", encoding="utf-8") as f:
                            cmd_text = f.read().strip()
                        os.remove(cmd_file)
                        if cmd_text:
                            is_silent = False
                            if cmd_text.startswith("SILENT:"):
                                is_silent = True
                                cmd_text = cmd_text[7:]
                            print(f"!!! STILLE TEXT-EINGABE EMPFANGEN: {cmd_text} !!!")
                            # Log it to session
                            t_stamp = time.strftime("%H:%M:%S")
                            with open(self.transcript_file, "a", encoding="utf-8") as f:
                                f.write(f"[{t_stamp}] [User (UI-Chat)]: {cmd_text}\n")
                                
                            self.trigger_action(cmd_text, silent_response=is_silent)
                            continue 
                    except Exception as e:
                        print(f"FEHLER BEI TEXT-EINGABE: {e}")

                # 2. Audio verarbeiten
                if getattr(self, 'mode', 'office') == 'chat':
                    time.sleep(0.2)
                    continue
                    
                try:
                    data = self.audio_queue.get(timeout=0.2)
                    audio_buffer.append(data)
                    
                    if len(audio_buffer) >= blocks_per_chunk:
                        audio_data = np.concatenate(audio_buffer).flatten().astype(np.float32)
                        audio_buffer = []

                        # VAD: Nur transkribieren wenn Lautstärke über Threshold
                        rms = np.sqrt(np.mean(audio_data**2))
                        
                        # --- DIAGNOSE: Lautstärke-Anzeige im Terminal ---
                        if self.show_volume_meter:
                            bar = "#" * int(rms * 500) + "." * max(0, 50 - int(rms * 500))
                            status = "✅" if rms >= self.silence_threshold else "🔇"
                            print(f"\rLevel: [{bar}] {rms:.4f} {status}", end="", flush=True)

                        if rms < self.silence_threshold:
                            if self.trigger_armed:
                                print("\n🔇 Stille erkannt. Führe Aktion aus...")
                                self.fire_trigger()
                            elif not (self.speak_process and self.speak_process.poll() is None):
                                set_state("idle")
                            continue
                        
                        # Laut genug -> Transkribieren
                        set_state("listening")
                        
                        # Transkribieren mit faster-whisper (small, beam_size=1 für Minimallatenz)
                        segments, _ = self._whisper.transcribe(
                            audio_data,
                            language="de",
                            initial_prompt=INITIAL_PROMPT,
                            condition_on_previous_text=False,
                            beam_size=1,   # Greedy-Decoding: 3-5x schneller
                            best_of=1
                        )
                        text = " ".join(s.text for s in segments).strip()
                        
                        # --- Erweiterter Halluzinations-Filter ---
                        lower_text = text.lower()
                        hallucinations = [
                            "vielen dank", "untertitel", "bitte abonnieren", 
                            "youtube", "zuschauen", "danke fürs zuhören",
                            "die ki-assistentin ist eine hochschule"
                        ]
                        
                        # 1. Bekannte Whisper-Halluzinationen bei Stille
                        if any(h in lower_text for h in hallucinations) and len(text) < 50:
                            continue
                        
                        # 2. Sinnlose Wort-Wiederholungen oder extrem kurze Fragmente (z.B. "implies.")
                        words = text.split()
                        if len(words) < 2 and len(text) < 10:
                            continue
                            
                        # Wort-Wiederholungs-Check (Whisper-Loop-Filter)
                        # Wenn ein Wort extrem oft vorkommt, ist es Quark
                        for word in set(words):
                            if words.count(word) > 4:
                                print(f"Skipping repetitive hallucination (Loop): {text[:30]}...")
                                text = "" # Mark for skipping
                                break
                        
                        if not text:
                            continue

                        if len(words) > 5 and len(set(words)) / len(words) < 0.4:
                            print(f"Skipping repetitive hallucination (Ratio): {text[:30]}...")
                            continue

                        if text:
                            self.process_text(text)
                except queue.Empty:
                    continue
        finally:
            if hasattr(self, 'audio_stream') and self.audio_stream:
                self.audio_stream.stop()
                self.audio_stream.close()

    def process_text(self, text):
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] {text}")
        
        # In Datei schreiben (immer, auch wenn stumm)
        with open(self.transcript_file, "a") as f:
            f.write(f"[{timestamp}] {text}\n")

        lower_text = text.lower()

        # Chunk zum Kontext-Ringpuffer hinzufügen
        self.recent_chunks.append(text)
        if len(self.recent_chunks) > 8:  # ~16-24 Sek. Kontext behalten
            self.recent_chunks.pop(0)

        # Unmute-Check: Auch im Stumm-Modus muss das Wake-Word erkannt werden
        if self.is_muted:
            if has_trigger(text, self.trigger_variants) and any(w in lower_text for w in [
                "wieder zuhören", "hör wieder zu", "hör zu", "unmute", "wieder hören",
                "kannst wieder", "jetzt wieder"
            ]):
                self.is_muted = False
                set_state("idle")
                print(f"🎙️ {self.agent_name} hört wieder zu!")
                subprocess.Popen(["say", "Ich bin wieder ganz Ohr."])
            return  # Im Stumm-Modus alles andere ignorieren
            
        # Trigger Check (Fuzzy)
        if has_trigger(text, self.trigger_variants):
            self.trigger_armed = True
            print(f"🎯 Wake-Word erkannt! Höre weiter zu... ({text})")
            
            # 🛑 Interrupt-Handling: Unterbreche laufende Sprachausgabe sofort
            if hasattr(self, 'speak_process') and self.speak_process and self.speak_process.poll() is None:
                self.speak_process.terminate()
                self.speak_process = None
                print("🛑 Laufende Sprachausgabe durch User-Interrupt unterbrochen!")
                
            set_state("listening") # Signalisiert, dass sie auf den restlichen Satz wartet
        else:
            # Nur auf Idle setzen, wenn sie gerade NICHT spricht und wir nicht auf das Ende eines Satzes warten
            if not self.trigger_armed and not (self.speak_process and self.speak_process.poll() is None):
                set_state("idle")

    def fire_trigger(self):
        if not self.trigger_armed:
            return
        self.trigger_armed = False
        
        # Falls sie gerade spricht, sofort abbrechen!
        if self.speak_process and self.speak_process.poll() is None:
            print(f"🛑 {self.agent_name.upper()} WURDE UNTERBROCHEN!")
            self.speak_process.kill()
            self.speak_process = None

        set_state("thinking")
        # Vollen Kontext übergeben (alle letzten Chunks), nicht nur den Trigger-Chunk
        full_context = " ".join(self.recent_chunks)
        # Aktuelle Anfrage = nur die letzten 3 Chunks (für Keyword-Erkennung im Router)
        recent_text = " ".join(self.recent_chunks[-3:])
        self.trigger_action(full_context, recent_text=recent_text)
        self.recent_chunks.clear()  # Reset nach Trigger

    def _speak_thread(self, text):
        set_state("speaking")
        
        target_device = self.audio_routing.get("private_device", "Standard")
        if "[SPEAKER]" in text:
            text = text.replace("[SPEAKER]", "").strip()
            target_device = self.audio_routing.get("public_device", "Standard")
            
        print(f"🔊 Trinity spricht (Device: {target_device}): {text[:60]}...")
        
        # Sicherstellen, dass der Text für die Shell sicher ist
        safe_text = text.replace('"', '').replace('$', '').replace('`', '')
        
        try:
            cmd = ["say"]
            if target_device != "Standard":
                try:
                    out = subprocess.check_output(["say", "-a", "?"], stderr=subprocess.STDOUT).decode("utf-8")
                    for line in out.strip().split("\n"):
                        parts = line.strip().split(" ", 1)
                        if len(parts) == 2 and parts[1] == target_device:
                            cmd.extend(["-a", parts[0]])
                            break
                except Exception as ex:
                    print("Warnung beim Auslesen der Audio-Geräte:", ex)
            cmd.append(safe_text)
            
            self.speak_process = subprocess.Popen(cmd)
            self.speak_process.wait()
        except Exception as e:
            print(f"⚠️ Fehler bei Sprachausgabe: {e}")
            
        if self.speak_process and self.speak_process.returncode == 0:
            set_state("idle")

    def switch_mode(self, new_mode):
        old_mode = getattr(self, 'mode', 'office')
        if old_mode == new_mode: return
        
        self.mode = new_mode
        self.system_cfg["mode"] = new_mode
        import json
        with open(self.config_path, "w") as f:
            with open(self.config_path, "r") as r:
                config = json.load(r)
            config["system"]["mode"] = new_mode
            json.dump(config, f, indent=2)
            
        if old_mode == 'chat' and new_mode != 'chat':
            if hasattr(self, 'audio_stream') and self.audio_stream:
                self.audio_stream.start()
                print("🎙️ Audio Stream gestartet.")
        elif old_mode != 'chat' and new_mode == 'chat':
            if hasattr(self, 'audio_stream') and self.audio_stream:
                self.audio_stream.stop()
                print("🛑 Audio Stream gestoppt.")

    def trigger_action(self, text, silent_response=False, recent_text=None, from_telegram=False):
        if getattr(self, 'mode', 'office') == 'chat':
            silent_response = True
            
        print(f"!!! TRIGGER GEFUNDEN: {text[-60:]} !!!")
        lower_text = text.lower()
        # recent_text = die letzten 2-3 Chunks (für präzise Keyword-Erkennung)
        action_text = (recent_text or text).lower()
        
        # UI-Befehle direkt abfangen (ohne LLM)
        # Modus-Wechsel
        if any(w in lower_text for w in ["büromodus aktivieren", "wechsle in den büromodus", "office modus"]):
            self.switch_mode("office")
            msg = "Büromodus aktiviert. Ich höre wieder aktiv zu."
            if not silent_response: subprocess.Popen(["say", msg])
            else: threading.Thread(target=self._silent_thread, args=(msg,), daemon=True).start()
            return
            
        if any(w in lower_text for w in ["vorlesungsmodus aktivieren", "wechsle in den vorlesungsmodus", "lecture modus"]):
            self.switch_mode("lecture")
            msg = "Vorlesungsmodus aktiviert. Ich lausche der Vorlesung."
            if not silent_response: subprocess.Popen(["say", msg])
            else: threading.Thread(target=self._silent_thread, args=(msg,), daemon=True).start()
            return
            
        if any(w in lower_text for w in ["chatmodus aktivieren", "wechsle in den chatmodus", "chat modus"]):
            self.switch_mode("chat")
            msg = "Chatmodus aktiviert. Mikrofon wurde deaktiviert."
            if not silent_response:
                subprocess.Popen(["say", msg])
            else:
                threading.Thread(target=self._silent_thread, args=(msg,), daemon=True).start()
            return

        if "mach dich unsichtbar" in lower_text or "versteck dich" in lower_text:
            set_state("invisible")
            if not silent_response: subprocess.Popen(["say", "Bin im Tarnmodus."])
            return
            
        if "mach dich sichtbar" in lower_text or "zeig dich" in lower_text:
            set_state("visible")
            set_state("idle")
            if not silent_response: subprocess.Popen(["say", "Bin wieder voll da, Partner."])
            return
            
        if "böse" in lower_text or "wütend" in lower_text or "sauer" in lower_text:
            set_state("angry")
            subprocess.Popen(["say", "Vorsicht, Partner. Reize mich lieber nicht."])
            # Revert nach 5 Sekunden
            threading.Timer(5.0, lambda: set_state("idle")).start()
            return

        if any(w in lower_text for w in ["lieb", "herz", "herzchen", "ich liebe", "süß", "knuddel", "küss", "bussi", "liebevoll", "herzlich", "hab dich lieb"]):
            set_state("love")
            subprocess.Popen(["say", "Aww. Du machst mich verlegen, Partner."])
            # Revert nach 5 Sekunden
            threading.Timer(5.0, lambda: set_state("idle")).start()
            return
            
        if "schließ" in lower_text and ("fenster" in lower_text or "timer" in lower_text or "anzeige" in lower_text):
            set_state("hide_window")
            if not silent_response:
                subprocess.Popen(["say", "Wird geschlossen."])
            return
            
        if "aktiviere text" in lower_text or "aktiviere untertitel" in lower_text or "schreib mit" in lower_text:
            self.text_mode = True
            if not silent_response:
                subprocess.Popen(["say", "Textmodus aktiviert. Ich werde meine Antworten jetzt auch einblenden."])
            return
            
        if "deaktiviere text" in lower_text or "deaktiviere untertitel" in lower_text or "schreib nicht mit" in lower_text:
            self.text_mode = False
            if not silent_response:
                subprocess.Popen(["say", "Textmodus deaktiviert."])
            return

        # Einstellungen öffnen
        if any(w in lower_text for w in ["einstellungen", "settings", "onboarding", "konfiguration"]):
            print("⚙️ Öffne Einstellungen...")
            subprocess.Popen([sys.executable, os.path.join(CORE_DIR, "settings_ui.py")])
            if not silent_response:
                subprocess.Popen(["say", "Ich öffne die Einstellungen für dich."])
            return

        # Stumm-Modus: Trinity hört auf zuzuhören
        if any(w in lower_text for w in ["hör nicht zu", "nicht zuhören", "sei still", "mute", "pause", "hör weg", "ohren zu"]):
            self.is_muted = True
            set_state("sleeping")
            print("🔇 Trinity ist jetzt stumm. Sage 'Trinity, hör wieder zu' zum Reaktivieren.")
            if not silent_response:
                subprocess.Popen(["say", "Alles klar, ich höre kurz weg. Sag einfach: Trinity, hör wieder zu."])
            return
            
        # Kontextbewusstes Feedback (non-blocking)
        if not silent_response:
            import random
            web_keywords = ["recherchier", "such ", "suche ", "finde heraus", "nächste spiel", "nächstes spiel", "spielplan", "nachricht", "online"]
            rag_keywords = ["laut skript", "im skript", "im buch", "laut buch", "wissensbasis", "schlag nach", "nachschlagen"]
            
            if any(w in action_text for w in web_keywords):
                filler = random.choice(["Ich schau kurz online nach.", "Einen Moment, ich recherchiere das.", "Ich such das kurz."])
            elif any(w in action_text for w in rag_keywords):
                filler = random.choice(["Ich schlag das nach.", "Ich check das im Skript."])
            else:
                filler = random.choice(["Hm.", "Sekunde.", "Warte kurz.", ""])
            
            if filler:
                threading.Thread(target=lambda: subprocess.Popen(["say", filler]).wait(), daemon=True).start()
        
        # Abfrage ans Gehirn senden
        use_text_mode = getattr(self, 'text_mode', False) or silent_response
        print(f"🧠 {self.agent_name} denkt nach über: '{text[-60:]}...'")
        antwort, has_payload = self.brain.ask(
            text, self.transcript_file,
            text_mode=use_text_mode, action_text=recent_text or text,
            from_telegram=from_telegram
        )

        print(f"💡 Trinity hat eine Antwort bereit ({len(antwort)} Zeichen).")
        
        # 🧠 Kontext-Gedächtnis: Trinitys eigene Antwort ins Transkript speichern!
        if antwort and len(antwort.strip()) > 0:
            with open(self.transcript_file, "a") as f:
                t_stamp = time.strftime("%H:%M:%S")
                f.write(f"[{t_stamp}] [{self.agent_name}]: {antwort}\n")
                
            # 📱 Telegram Feedback: Antwort zurückschicken, falls von dort angetriggert
            if from_telegram and self.telegram_cfg.get("enabled", False):
                try:
                    import requests
                    tg_url = f"https://api.telegram.org/bot{self.telegram_cfg['bot_token']}/sendMessage"
                    requests.post(tg_url, json={
                        "chat_id": self.telegram_cfg["chat_id"],
                        "text": f"*{self.agent_name} antwortet:*\n{antwort}"
                    }, timeout=5)
                except Exception as e:
                    print(f"⚠️ Fehler beim Senden der Telegram-Antwort: {e}")
        
        # Antwort bereinigen
        sichere_antwort = re.sub(r'[*_#]', '', antwort)
        sichere_antwort = sichere_antwort.replace('\n', ' ').replace("'", "").replace('"', "")
        # Verhindern, dass sie sich selbst triggert, falls ihr Audio doch ins Mikrofon gelangt:
        sichere_antwort = sichere_antwort.replace(self.agent_name, "ich")
        
        # Wenn wir ein Payload haben, soll das UI es anzeigen (Reporting Mode)
        if has_payload:
            set_state("reporting")
            # Wir warten kurz, damit das UI Zeit hat, das Fenster aufzubauen
            time.sleep(0.5)
            
        if silent_response:
            threading.Thread(target=self._silent_thread, args=(sichere_antwort,), daemon=True).start()
        else:
            threading.Thread(target=self._speak_thread, args=(sichere_antwort,), daemon=True).start()

    def _silent_thread(self, text):
        set_state("speaking") # Augen-Animation (optional)
        words = len(text.split())
        reading_time = max(3.0, words * 0.3) # 300ms pro Wort Lesezeit
        time.sleep(reading_time)
        set_state("idle")

if __name__ == "__main__":
    ear = MorpheusEar()
    try:
        ear.start()
    except KeyboardInterrupt:
        print("\nMorpheus geht schlafen.")

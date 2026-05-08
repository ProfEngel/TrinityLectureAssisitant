from faster_whisper import WhisperModel
import sounddevice as sd
import numpy as np
import os
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
        
        # Neues Transkript für diese Sitzung anlegen
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        self.transcript_file = os.path.join(MEMORY_DIR, f"Sitzung_{timestamp}.md")
        with open(self.transcript_file, "w") as f:
            f.write(f"# Trinity Session Log - {timestamp}\n\n")
            
        print(f"Lade Whisper Modell ({self.model_name}) via faster-whisper...")
        # int8 = quantisiert, cpu = Apple Silicon kompatibel, download_root cached das Modell
        self._whisper = WhisperModel(self.model_name, device="cpu", compute_type="int8")
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
            self.voice = config["tts"]["voice"]
            # Persona-Config laden
            persona = config.get("persona", {})
            self.agent_name = persona.get("agent_name", TRIGGER_WORD)
            self.trigger_variants = persona.get("trigger_variants", TRIGGER_VARIANTS)
        except:
            self.model_name = MODEL
            self.silence_threshold = SILENCE_THRESHOLD
            self.chunk_duration = CHUNK_DURATION
            self.voice = "Samantha"
            self.agent_name = TRIGGER_WORD
            self.trigger_variants = TRIGGER_VARIANTS
        
    def audio_callback(self, indata, frames, time, status):
        """Wird vom sounddevice Stream aufgerufen."""
        if status:
            print(f"Audio Error: {status}")
        # Wir sammeln IMMER Audio, auch wenn sie spricht, um Unterbrechungen zu ermöglichen
        self.audio_queue.put(indata.copy())

    def start(self):
        self.is_running = True
        set_state("idle")
        
        cmd_file = os.path.join(os.path.dirname(__file__), "cmd.txt")
        # Wir lesen in kleineren Häppchen (0.5s), um stabiler zu sein
        block_size = int(SAMPLE_RATE * 0.5)
        blocks_per_chunk = int(self.chunk_duration / 0.5)
        
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, callback=self.audio_callback, blocksize=block_size):
            print(f"Trinity hört jetzt zu... (Model: {self.model_name}, Thresh: {self.silence_threshold})")
            
            audio_buffer = []
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
                            self.trigger_action(cmd_text, silent_response=is_silent)
                            continue 
                    except Exception as e:
                        print(f"FEHLER BEI TEXT-EINGABE: {e}")

                # 2. Audio verarbeiten
                try:
                    data = self.audio_queue.get(timeout=1)
                    audio_buffer.append(data)
                    
                    if len(audio_buffer) >= blocks_per_chunk:
                        audio_data = np.concatenate(audio_buffer).flatten().astype(np.float32)
                        audio_buffer = []

                        # VAD: Nur transkribieren wenn Lautstärke über Threshold
                        rms = np.sqrt(np.mean(audio_data**2))

                        if rms < self.silence_threshold:
                            if not (self.speak_process and self.speak_process.poll() is None):
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
        else:
            # Nur auf Idle setzen, wenn sie gerade NICHT spricht
            if not (self.speak_process and self.speak_process.poll() is None):
                set_state("idle")

    def _speak_thread(self, text):
        set_state("speaking")
        print(f"🔊 Trinity spricht: {text[:60]}...")
        
        # Sicherstellen, dass der Text für die Shell sicher ist
        safe_text = text.replace('"', '').replace('$', '').replace('`', '')
        
        try:
            # Nutzt die macOS Systemstimme (deine voreingestellte Siri Stimme)
            self.speak_process = subprocess.Popen(["say", safe_text])
            self.speak_process.wait()
        except Exception as e:
            print(f"⚠️ Fehler bei Sprachausgabe: {e}")
            
        if self.speak_process and self.speak_process.returncode == 0:
            set_state("idle")

    def trigger_action(self, text, silent_response=False, recent_text=None):
        print(f"!!! TRIGGER GEFUNDEN: {text[-60:]} !!!")
        lower_text = text.lower()
        # recent_text = die letzten 2-3 Chunks (für präzise Keyword-Erkennung)
        action_text = (recent_text or text).lower()
        
        # UI-Befehle direkt abfangen (ohne LLM)
        if "mach dich unsichtbar" in lower_text or "versteck dich" in lower_text:
            set_state("invisible")
            subprocess.Popen(["say", "Bin im Tarnmodus."])
            return
            
        if "mach dich sichtbar" in lower_text or "zeig dich" in lower_text:
            set_state("visible")
            set_state("idle")
            subprocess.Popen(["say", "Bin wieder voll da, Partner."])
            return
            
        if "böse" in lower_text or "wütend" in lower_text or "sauer" in lower_text:
            set_state("angry")
            subprocess.Popen(["say", "Vorsicht, Partner. Reize mich lieber nicht."])
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
        antwort, has_payload = self.brain.ask(text, self.transcript_file, text_mode=use_text_mode, action_text=recent_text or text)
        print(f"💡 Trinity hat eine Antwort bereit ({len(antwort)} Zeichen).")
        
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

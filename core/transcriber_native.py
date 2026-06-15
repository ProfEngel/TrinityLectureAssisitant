"""
Native macOS STT loop for Trinity.

This module uses Apple's Speech framework for transcription and reuses the
existing MorpheusEar command handling, memory logging, LLM routing, and TTS
behavior from transcriber.py. It intentionally does not load a Whisper model.
"""
import os
import queue
import sys
import threading
import time

from Foundation import NSDate, NSLocale, NSRunLoop
from Speech import (
    SFSpeechAudioBufferRecognitionRequest,
    SFSpeechRecognizer,
    SFSpeechRecognizerAuthorizationStatusAuthorized,
)
from AVFoundation import AVAudioEngine

sys.path.append(os.path.dirname(__file__))
from brain import TrinityBrain
from platform_adapters import create_tts_backend
from transcriber import MEMORY_DIR, MorpheusEar, set_state


class NativeMorpheusEar(MorpheusEar):
    """MorpheusEar variant backed by macOS SFSpeechRecognizer."""

    def __init__(self):
        self.brain = TrinityBrain()
        self.config_path = os.path.join(os.path.dirname(__file__), "config.json")
        self.load_config()
        self.tts_backend = create_tts_backend()

        self.audio_queue = queue.Queue()
        self.is_running = False
        self.uses_native_speech = True
        self.speak_process = None
        self.recent_chunks = []
        self.is_muted = False
        self.text_mode = False

        timestamp = time.strftime("%d%b%Y_%H%M")
        self.transcript_file = os.path.join(MEMORY_DIR, f"raw_session_{timestamp}.md")
        with open(self.transcript_file, "w", encoding="utf-8") as f:
            f.write(f"# Trinity Native Session Log - {timestamp}\n\n")

        self.audio_engine = None
        self.recognition_request = None
        self.recognition_task = None
        self.recognizer = None
        self._last_final_text = ""
        print("✅ Native macOS Spracherkennung vorbereitet.")

    def _run_loop_tick(self, seconds=0.1):
        until = NSDate.dateWithTimeIntervalSinceNow_(seconds)
        NSRunLoop.currentRunLoop().runUntilDate_(until)

    def _request_authorization(self):
        done = threading.Event()
        result = {"status": None}

        def handler(status):
            result["status"] = status
            done.set()

        SFSpeechRecognizer.requestAuthorization_(handler)
        while not done.is_set():
            self._run_loop_tick()
        return result["status"] == SFSpeechRecognizerAuthorizationStatusAuthorized

    def _handle_result(self, result, error):
        if error is not None:
            print(f"⚠️ Native STT Fehler: {error}")
            return
        if result is None:
            return

        text = str(result.bestTranscription().formattedString()).strip()
        if not text:
            return

        if result.isFinal():
            # Finales Ergebnis → in Transkript schreiben + Wake-Word prüfen
            if text != self._last_final_text:
                self._last_final_text = text
                self.process_text(text)
        else:
            # Partial → nur im Terminal anzeigen für Live-Feedback
            print(f"\r🎙️ {text}", end="", flush=True)

    def _start_recognition(self):
        self.recognizer = SFSpeechRecognizer.alloc().initWithLocale_(
            NSLocale.localeWithLocaleIdentifier_("de-DE")
        )
        if self.recognizer is None or not self.recognizer.isAvailable():
            raise RuntimeError("SFSpeechRecognizer ist nicht verfügbar.")

        self.audio_engine = AVAudioEngine.alloc().init()
        self.recognition_request = SFSpeechAudioBufferRecognitionRequest.alloc().init()
        self.recognition_request.setShouldReportPartialResults_(True)

        input_node = self.audio_engine.inputNode()
        recording_format = input_node.outputFormatForBus_(0)

        def tap_block(buffer, when):
            self.recognition_request.appendAudioPCMBuffer_(buffer)

        input_node.installTapOnBus_bufferSize_format_block_(0, 1024, recording_format, tap_block)
        self.audio_engine.prepare()

        started = self.audio_engine.startAndReturnError_(None)
        if isinstance(started, tuple):
            ok, error = started
        else:
            ok, error = started, None
        if not ok:
            raise RuntimeError(f"AudioEngine konnte nicht starten: {error}")

        self.recognition_task = self.recognizer.recognitionTaskWithRequest_resultHandler_(
            self.recognition_request,
            self._handle_result,
        )

    def _stop_recognition(self):
        try:
            if self.audio_engine is not None and self.audio_engine.isRunning():
                self.audio_engine.stop()
                self.audio_engine.inputNode().removeTapOnBus_(0)
            if self.recognition_request is not None:
                self.recognition_request.endAudio()
            if self.recognition_task is not None:
                self.recognition_task.cancel()
        except Exception as exc:
            print(f"⚠️ Fehler beim Stoppen der Native-STT: {exc}")

    def switch_mode(self, new_mode):
        old_mode = getattr(self, 'mode', 'office')
        if old_mode == new_mode: return
        
        super().switch_mode(new_mode)
        
        if old_mode == 'chat' and new_mode != 'chat':
            if self._request_authorization():
                self._start_recognition()
                print("🎙️ Native Audio Stream gestartet.")
        elif old_mode != 'chat' and new_mode == 'chat':
            self._stop_recognition()
            print("🛑 Native Audio Stream gestoppt.")

    def start(self):
        self.is_running = True
        set_state("idle")

        cmd_file = os.path.join(os.path.dirname(__file__), "cmd.txt")
        
        # Start Heartbeat Thread only if enabled AND not in chat mode
        mode = getattr(self, 'mode', 'office')
        if getattr(self, 'proactive_cfg', {}).get("heartbeat_enabled", False) and mode != "chat":
            threading.Thread(target=self._heartbeat_loop, daemon=True).start()
            
        # Start Telegram Listener Thread if enabled
        if getattr(self, 'telegram_cfg', {}).get("enabled", False) and getattr(self, 'telegram_cfg', {}).get("bot_token"):
            threading.Thread(target=self._telegram_listener_loop, daemon=True).start()

        mode = getattr(self, 'mode', 'office')
        if mode == 'chat':
            print("💬 Chat-Modus aktiv: macOS Native STT bleibt deaktiviert. Höre nur auf UI (Flüstern) oder Telegram.")
        else:
            if not self._request_authorization():
                print("❌ Keine Berechtigung für macOS-Spracherkennung.")
                self._speak_quick("Ich brauche Zugriff auf die Spracherkennung.")
                return

            print("Trinity hört nativ via macOS SFSpeechRecognizer zu...")
            self._start_recognition()

        try:
            while self.is_running:
                if os.path.exists(cmd_file):
                    try:
                        with open(cmd_file, "r", encoding="utf-8") as f:
                            cmd_text = f.read().strip()
                        os.remove(cmd_file)
                        if cmd_text:
                            is_silent = cmd_text.startswith("SILENT:")
                            if is_silent:
                                cmd_text = cmd_text[7:]
                                
                            if getattr(self, 'mode', 'office') == 'chat':
                                is_silent = True
                                
                            print(f"!!! STILLE TEXT-EINGABE EMPFANGEN: {cmd_text} !!!")
                            
                            # Log it to session
                            t_stamp = time.strftime("%H:%M:%S")
                            with open(self.transcript_file, "a", encoding="utf-8") as f:
                                f.write(f"[{t_stamp}] [User (UI-Chat)]: {cmd_text}\n")
                                
                            self.trigger_action(cmd_text, silent_response=is_silent)
                    except Exception as exc:
                        print(f"FEHLER BEI TEXT-EINGABE: {exc}")
                self._run_loop_tick()
        finally:
            self._stop_recognition()


if __name__ == "__main__":
    ear = NativeMorpheusEar()
    try:
        ear.start()
    except KeyboardInterrupt:
        print("\nMorpheus Native geht schlafen.")

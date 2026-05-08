"""
TrinityNative Launcher
STT: macOS SFSpeechRecognizer (Apple Neural Engine, Deutsch)
LLM: identisch zu Legacy Trinity (brain.py + Soul.md)
UI:  identisch zu Legacy Trinity (trinity_app.py)

Starten: python3 projects/Trinity_Assistant/trinity_native_launcher.py
Legacy:  python3 projects/Trinity_Assistant/trinity_launcher.py  (unverändert)
"""
import subprocess
import sys
import time
import os
from threading import Thread

def launch_trinity_native():
    print("🧞‍♀️ Starte TrinityNative (macOS Neural Engine STT)...")

    base_dir   = os.path.dirname(os.path.abspath(__file__))
    ui_script  = os.path.join(base_dir, "trinity_app.py")
    ear_script = os.path.join(base_dir, "core", "transcriber_native.py")
    config_file = os.path.join(base_dir, "core", "config.json")
    settings_script = os.path.join(base_dir, "core", "settings_ui.py")

    if not os.path.exists(config_file):
        print("⚙️ Erstes Setup erkannt. Öffne Konfiguration...")
        subprocess.run([sys.executable, settings_script])
        if not os.path.exists(config_file):
            print("❌ Konfiguration abgebrochen. Beende Trinity.")
            sys.exit(1)

    print("-> Aktiviere das Gehör (macOS SFSpeechRecognizer, Deutsch)...")
    ear_process = subprocess.Popen(
        [sys.executable, ear_script],
        stdout=sys.stdout, stderr=sys.stderr  # Output direkt ins Terminal
    )

    print("-> Rufe den Avatar (UI)...")
    ui_process = subprocess.Popen(
        [sys.executable, ui_script],
        stdout=sys.stdout, stderr=sys.stderr
    )

    print("\n✅ TrinityNative ist aktiv und hört zu.")
    print("   STT: macOS Neural Engine (kein Whisper, kein Modell-Download)")
    print("   Drücke Strg+C zum Beenden.\n")

    try:
        while True:
            if ui_process.poll() is not None:
                print("UI geschlossen. Beende...")
                break
            if ear_process.poll() is not None:
                print("Gehör-Prozess abgebrochen. Beende...")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping TrinityNative...")
    finally:
        ui_process.terminate()
        ear_process.terminate()
        print("TrinityNative schläft. Bis zum nächsten Mal!")

if __name__ == "__main__":
    launch_trinity_native()

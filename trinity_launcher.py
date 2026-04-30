import subprocess
import sys
import time
import os

def launch_trinity():
    print("🧞‍♀️ Starte Trinity System...")
    
    # 1. Pfade definieren
    base_dir = os.path.dirname(os.path.abspath(__file__))
    ui_script = os.path.join(base_dir, "trinity_app.py")
    ear_script = os.path.join(base_dir, "core", "transcriber.py")

    # 2. Prozesse starten
    print("-> Aktiviere das Gehör (Whisper)...")
    ear_process = subprocess.Popen([sys.executable, ear_script])
    
    print("-> Rufe den Avatar (UI)...")
    ui_process = subprocess.Popen([sys.executable, ui_script])

    print("\n✅ Trinity ist jetzt aktiv und hört zu.")
    print("Drücke Strg+C zum Beenden.")

    try:
        # Halte das Skript am Laufen, solange die Prozesse leben
        while True:
            if ui_process.poll() is not None:
                print("UI wurde geschlossen. Beende System...")
                break
            if ear_process.poll() is not None:
                print("Gehör-Prozess abgebrochen. Starte neu oder beende...")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping Trinity...")
    finally:
        ui_process.terminate()
        ear_process.terminate()
        print("Trinity ist schlafen gegangen.")

if __name__ == "__main__":
    launch_trinity()

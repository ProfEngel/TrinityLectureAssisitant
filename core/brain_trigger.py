import time
import os

def simulate_trigger():
    print("Suche nach Keywords im Transkript...")
    transcript_file = "lecture_transcript.md"
    
    if not os.path.exists(transcript_file):
        return

    with open(transcript_file, "r") as f:
        lines = f.readlines()
        if any("Trinity" in line for line in lines):
            print("!!! TRIGGER ERKANNT: Trinity wurde gerufen !!!")
            # Hier würde der OpenClaw Call erfolgen
            return True
    return False

if __name__ == "__main__":
    while True:
        if simulate_trigger():
            print("Aktion: Starte Recherche-Subagent...")
            break
        time.sleep(1)

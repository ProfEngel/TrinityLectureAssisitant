import time
import os

class MorpheusEar:
    """
    Diese Klasse simuliert oder integriert den Whisper-MLX Stream.
    In der finalen Version wird hier der CoreAudio-Stream an MLX übergeben.
    """
    def __init__(self, transcript_path="lecture_transcript.md"):
        self.transcript_path = transcript_path
        # Datei initialisieren
        with open(self.transcript_path, "w") as f:
            f.write("# Morpheus Live-Transkript\n\n")

    def start_listening(self):
        print("Morpheus hört zu...")
        # Hier käme der MLX-Loop hin. 
        # Für den Prototyp simulieren wir ein paar Zeilen:
        self.append_to_transcript("Willkommen zur heutigen Vorlesung über Künstliche Intelligenz.")
        time.sleep(2)
        self.append_to_transcript("Wir schauen uns heute Agenten-Systeme an.")
        time.sleep(3)
        self.append_to_transcript("Morpheus, recherchiere mal kurz, was die neuesten Benchmarks für Gemma 2 sind.")

    def append_to_transcript(self, text):
        timestamp = time.strftime("%H:%M:%S")
        with open(self.transcript_path, "a") as f:
            f.write(f"[{timestamp}] {text}\n")
        print(f"Transcript updated: {text}")

if __name__ == "__main__":
    ear = MorpheusEar()
    ear.start_listening()

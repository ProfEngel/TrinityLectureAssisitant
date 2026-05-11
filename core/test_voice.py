import subprocess


def speak(text):
    """
    Nutzt das native macOS 'say' Kommando.
    Dies ist die schnellste und einfachste Methode für Siri-Stimmen auf dem Mac.
    """
    print(f"Morpheus sagt: {text}")
    # -v 'Anna' (Deutsch), -v 'Siri' (falls konfiguriert)
    # Wir nutzen den Standardwert des Systems.
    subprocess.run(["say", text], check=False)


if __name__ == "__main__":
    speak("Hallo Mat Max. Ich bin Morpheus. Dein neuer Assistent ist bereit.")

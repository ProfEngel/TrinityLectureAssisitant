from platform_adapters import create_tts_backend


def speak(text):
    """Test the native TTS backend for the current operating system."""
    print(f"Morpheus sagt: {text}")
    create_tts_backend().speak(text).wait()


if __name__ == "__main__":
    speak("Hallo Mat Max. Ich bin Morpheus. Dein neuer Assistent ist bereit.")

from platform_adapters import create_tts_backend


def speak(text):
    """Test the native TTS backend for the current operating system."""
    print(f"Trinity sagt: {text}")
    create_tts_backend().speak(text).wait()


if __name__ == "__main__":
    speak("Hallo Mat Max. Ich bin Trinity. Dein neuer Assistent ist bereit.")

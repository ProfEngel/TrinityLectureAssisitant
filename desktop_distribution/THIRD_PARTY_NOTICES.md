# Desktop starter: third-party notices

Trinity source: Apache License 2.0. The starter dynamically links Qt/PySide6
6.11.1 under LGPLv3; Python uses the PSF license; uv 0.11.2 uses MIT/Apache 2.0.
PyInstaller 6.16.0 uses GPLv2 with its bootloader exception. These components
do not relicense the Trinity source. License texts are included alongside this
notice in `resources/licenses/` inside the application. Qt libraries remain
separate dynamically loaded files: replacement/modification for your use is
not prohibited. Keep your replacements compatible; macOS may need local
re-signing after changing an app bundle.

Corresponding upstream sources:

- Qt: https://download.qt.io/official_releases/qt/6.11/
- PySide/Shiboken: https://code.qt.io/cgit/pyside/pyside-setup.git/?h=6.11.1
- uv: https://github.com/astral-sh/uv/tree/0.11.2
- PyInstaller: https://github.com/pyinstaller/pyinstaller/tree/v6.16.0
- CPython: https://www.python.org/downloads/source/

Installed speech engines and models are downloaded during first-run setup;
their package/model distributions include their own licenses. They are not
relicensed by Trinity. In particular:

- speech-to-speech 0.2.11: Apache 2.0,
  https://github.com/huggingface/speech-to-speech
- Parakeet v3 / NVIDIA: model license on its Hugging Face model card,
  https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3
- Qwen3-TTS: Apache 2.0,
  https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base
- Eve reference: `assets/voices/eve/INITIAL_VOICE_LICENSE.md`.

The release does not contain private MP3 decks, user conversations, API keys
or proprietary LLM weights. Configure any external services separately.

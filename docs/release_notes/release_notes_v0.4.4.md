# Release Notes v0.4.4 - Bugfix Update 🧞‍♀️

Dieses Release konzentriert sich auf die Behebung kleinerer technischer Mängel und die Verbesserung der Systemstabilität.

## 🛠 Änderungen & Fixes

- **Core-Stabilität**: Umstellung von `os.system` auf `subprocess.run` in den Voice-Komponenten für eine sicherere Prozesssteuerung.
- **Dependency Update**: `pyobjc-framework-AVFoundation` wurde als explizite Abhängigkeit im Installer (`install_mac.sh`) und in der Dokumentation hinzugefügt, um Probleme mit der Audio-Schnittstelle auf neueren macOS-Versionen zu vermeiden.
- **UI-Bereinigung**: Korrektur der `payload.html` Template-Logik.
- **Native Support**: Vorbereitungen für `transcriber_native.py` zur besseren Integration in macOS-Audio-Services.

---
*Optimiert für macOS Apple Silicon. Viel Spaß mit Trinity!*

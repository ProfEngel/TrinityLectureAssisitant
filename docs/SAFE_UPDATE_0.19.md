# Sicheres Update auf 0.19

Nicht eine neue Beispielkonfiguration über die bestehende Installation kopieren.
Vorher privaten Snapshot von Code, `core/config.json`, `Soul.md`, `User.md`,
Memory-/Runtime-Verzeichnissen, Secrets und eigenen Stimmreferenzen anlegen.
Backup nicht in Git oder ein Release hochladen.

In einen getrennten Checkout installieren, Abhängigkeiten und Diagnose prüfen,
dann nur geprüften Programmcode übernehmen. Bestehende Startpfade/Dienste,
Ports, Profile, Modellnamen und Audioverbindungen gezielt kontrollieren.
Zum Rückrollen Code und Abhängigkeiten aus dem Snapshot restaurieren; weder
Memory löschen noch die aktuelle Konfiguration unbesehen durch ältere ersetzen.

Linux kann selbst der vollständige Server sein:

```sh
trinity server --host YOUR_PRIVATE_IP --port 8765 --voice-profile trinity-linux-server
```

LLM-Endpunkt, Eve/Qwen3-Referenz, NVIDIA-Abhängigkeiten und Schutz für Bridge
und Voice müssen vorher konfiguriert sein. Ein Systemdienst benötigt seinen
korrekten Arbeitsordner, Python-Pfad, Restart-Regel und Netzwerkverfügbarkeit.
Keine Ports öffentlich am Router freigeben. Windows-VM nicht erforderlich.

Mac-Client: Server-/Voice-Adressen und vorhandene Tokens beibehalten;
`trinity-mac-client` verwendet den zentralen Server. Standalone bleibt möglich.
Windows-Standalone und alte Windows-GPU-Remote-Profile bleiben im Code, sind
kein Anlass, einen bereits funktionierenden Serveraufbau zu überschreiben.

## Kopierbarer Windows-Auftrag

> Aktualisiere meine vorhandene Trinity auf den Release Candidate
> `v0.19.0-rc.1` aus ProfEngel/TrinityLectureAssisitant. Prüfe zuerst Startpfad,
> Git-Status, Betriebsprofil, Modell-/STT-/TTS-Endpunkte und Autostart. Erstelle
> einen privaten rückrollbaren Snapshot. Erhalte alle vorhandenen Verbindungen,
> Passwörter/Tokens, Soul/User, Memory, Runtime und Eve-Stimmreferenz. Übernimm
> nur geprüften Code und benötigte Abhängigkeiten; kopiere keine Beispielkonfig
> darüber. Wenn diese Installation Client ist, bleibe Client des bestehenden
> Linux-Servers; starte kein zweites Parakeet/LLM/TTS. Prüfe Diagnosen, Antwort
> auf Korrelation/Kausalität, Umlaute, Gerätewechsel und Vision. Beschreibe
> ungetestete Windows-Funktionen ehrlich. Bei Fehlern rolle den Programmcode
> zurück, ohne Daten/Verbindungen zu löschen. Keine privaten Dateien committen.

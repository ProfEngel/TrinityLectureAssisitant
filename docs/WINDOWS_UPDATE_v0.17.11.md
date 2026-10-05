# Sichere Windows-BIZ-Aktualisierung auf v0.17.11

Dieses Update ergänzt Foliensehen und Desktop-Bedienung. Es verlangt weder eine
neue Eve-Installation noch andere Verbindungsdaten. Die reale Installation muss
vor Änderungen geprüft werden: lokale Fixes können neuer als der Release sein.

## Prompt für den ausführenden Windows-Agenten

Aktualisiere meine vorhandene BIZ-Trinity unter Windows 11 in einer VM auf einem
Ubuntu-PC auf das Desktop-Release v0.17.11 aus
https://github.com/ProfEngel/TrinityLectureAssisitant.
Ziel ist vor allem das Sehen der aktuell auf dem iPad geöffneten Vortragsfolie
bei Sprach- und Chatfragen. Bewahre das bestehende funktionierende System.

### 1. Zuerst nur Bestandsaufnahme

- Lies die lokalen AGENTS.md-Dateien, die Release Notes und diese Anleitung.
- Ermittle den echten Installations-/Startpfad, Git-Stand und lokale Änderungen,
  Python-/venv-Pfad, Startmechanismus, BIZ-Profil sowie tatsächliche Runtime-,
  Memory-, Datenbank-, RAG-, Agenten- und Vault-Pfade. Keine Pfade erraten.
- Ermittle den tatsächlichen Sprachweg: Mikrofon/STT → Trinity-Core/Modell →
  Eve/TTS → Ausgabegerät, einschließlich eines gegebenenfalls getrennten Ubuntu-Hosts.
- Protokolliere die Konfiguration lokal geschützt; zeige keine Tokens, Passwörter,
  API-Schlüssel oder vollständigen vertraulichen Inhalte im Chat oder Git-Diff.
- Prüfe vorab die bisher funktionierenden Funktionen und halte die Ergebnisse fest.

### 2. Verbindlich unverändert lassen

- core/config.json und andere aktive Konfigurationsdateien, .env und Secrets;
- BIZ-Profil, Verbindungsprofile, Bridge-/Voice-Tokens, Modellslots und URLs,
  Tailscale-Adressen, Ports, Firewall, TLS und Authentifizierung;
- Eve-Stimme/Referenzaudio, Modellgewichte, Cache, STT-/TTS-Auswahl, Audiohardware,
  bestehende Python-/CUDA-/Torch-Umgebung und den Ubuntu-Server;
- Soul.md, User.md, Memory, SQLite-Datenbanken, Sessions, Notizen, RAG-Indizes,
  persönliche/berufliche Bestandsinformationen, eigene Agenten, BizVault und OneDrive;
- Autostart und funktionierende lokale Fehlerkorrekturen.

Kein install_windows.ps1 oder install_voice_windows.ps1 als pauschales Update.
Keine Neuinstallation von Eve, kein blindes pip upgrade, kein git reset --hard,
kein git clean, kein Löschen von Daten, kein Übernehmen einer Mac-Konfiguration.
Ein Git-Stash allein ist keine Datensicherung.

### 3. Sicherung und Updateplan

- Prüfe zuerst, ob Aufträge laufen. Beende Trinity zur konsistenten Sicherung
  kontrolliert; beende keine fremden Python-/Node-Prozesse.
- Sichere die Installation einschließlich lokaler Änderungen, venv beziehungsweise
  reproduzierbarem Abhängigkeitsstand, Konfiguration und tatsächlich verwendeten
  Laufzeitdaten in einem separaten geschützten Bereich. Sichere SQLite nur bei
  gestoppten Schreibern oder mit der SQLite-Backup-API; WAL-Dateien beachten.
- Lasse vor dem produktiven Austausch möglichst einen VM-Snapshot erstellen.
  Durchgereichte, externe und synchronisierte Ablagen sind dadurch nicht automatisch
  gesichert. Ohne verifizierte Sicherung und konkreten Rückrollweg nicht fortfahren.
- Lade v0.17.11 in ein separates Verzeichnis, verifiziere Tag/Commit gegen GitHub
  und prüfe den Diff gegenüber dem tatsächlich laufenden Stand. Verwende nicht
  ungeprüft den dann aktuellen main-Branch und kopiere kein ganzes Archiv darüber.
- Lege eine genaue Liste der zu ändernden Code-Dateien vor. Bei Überschneidungen
  mit lokalen Fixes diese erhalten und gezielt integrieren. Bei unbekannten
  Konflikten oder erforderlichen Konfigurations-/Dependency-Änderungen anhalten
  und nachfragen. Erst nach Freigabe des konkreten Plans produktiv anwenden.

### 4. Abnahme und Rückrollregel

- Quellcode kompilieren und relevante Tests aus dem Release mit der bestehenden
  kompatiblen Umgebung ausführen; fehlende Testwerkzeuge ggf. nur isoliert installieren.
- Insbesondere tests/test_lecture_context.py, tests/test_lecture_voice_integration.py,
  tests/test_desktop_audio_activity.py, tests/test_trinity_bridge.py und die vorhandenen
  Tests des tatsächlich verwendeten Voice-Backends prüfen.
- Prüfe geschützte Konfigurationsdateien vor/nach dem Update per Hash bzw. redigiertem
  Vergleich. Bestehende Datensätze müssen erhalten bleiben; keine neue leere Runtime
  anstelle der vorhandenen verwenden. Für reine Tests nur isolierte Testdaten nutzen.
- Starte Windows-Trinity mit dem bisherigen Startmechanismus. Prüfe Chat, Mikrofon,
  STT, unveränderte Eve-Stimme, richtige Ausgabe, iPad-Verbindung und wichtige Agenten.
- Auf dem iPad BIZ wählen, dieselbe Windows-Bridge und authentifizierten Zugang
  verwenden und Foliensehen aktivieren. Unter Settings muss ein Bild bestätigt sein.
- Eine reale Folie mit eindeutiger Tabelle öffnen, einen Wert per Chat UND Sprache
  abfragen, zur nächsten Folie wechseln und erneut prüfen. Verlassen/Profilwechsel
  dürfen keine alte oder profilfremde Folie als aktuell weiterreichen.
- Neu starten und Autostart/Verbindungen nochmals prüfen. Kein Port darf zusätzlich
  öffentlich freigegeben werden. Änderungen an Ubuntu sind nicht vorausgesetzt.
- Bei Regressionen die betroffene Instanz stoppen und den gesicherten vorherigen
  Code-/Umgebungsstand wiederherstellen. Seit der Sicherung neu entstandene Nutzerdaten
  vorher separat schützen; nicht blind einen VM-Snapshot über neue Arbeit zurückrollen.
- Abschluss: Tag/Commit, geänderte Dateien, Sicherungspfad, erhaltene Einstellungen,
  Testergebnisse und offene Punkte nennen. Ohne erfolgreichen realen Sprachtest
  nicht behaupten, Eve und Foliensehen seien vollständig abgenommen.

Falls du keinen lokalen Datei-/Terminalzugriff auf die Windows-VM hast: nichts als
erledigt ausgeben, sondern einen lokal ausführenden Agenten bzw. Zugriff anfordern.

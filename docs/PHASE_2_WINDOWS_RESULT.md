# Phase 2 – Windows-Ergebnis und kontrollierte Nacharbeit

Stand: 22. Juli 2026
T0-Nachprüfung: 23. Juli 2026

## Ergebnis

Die technische Windows-Inventur und der rückholbare BIZ-Testreset sind
abgeschlossen:

- Profil: `BIZ`, sichtbar als **Arbeit**
- Installation: `C:\Users\matmax\AppData\Local\Trinity`
- Runtime: `C:\Users\matmax\AppData\Local\Trinity\TrinityRuntime`
- vorgesehener Inhalts-Vault:
  `C:\Users\matmax\OneDrive - Hochschule für Wirtschaft und Umwelt\BizVault`
- Recovery: `C:\Users\matmax\Trinity-Recovery\reset-biz-2026-07-22_124730`
- Memory nach Reset: 0 Sessions, 0 Nachrichten, 0 Memories, 0 Tags und
  0 Beziehungen
- genau eine neue, leere gemeinsame Session
- Canvas gebündelt, automatisch gestartet und per HTTP 200 erreichbar
- Telegram-Bot Arbeit erreichbar: `Trinity_HFWU_bot`, Fingerprint
  `02N8LCwzPked`
- BizVault, Konfiguration, Soul, User und RAG-Dateien blieben beim Reset
  unverändert

Die T0-Nachprüfung auf Windows hat den fehlenden Versions- und
Installationsnachweis ergänzt:

- Trinity: `0.16.58`, laut Online-Doctor aktuell
- Python: `3.11.9`
- SSL: OpenSSL `3.0.13`
- Oberflächen: Eyes und Terminal; PySide6 verfügbar
- lokaler LLM-Provider konfiguriert
- Goose verfügbar
- Codex CLI nicht installiert
- OpenCode CLI nicht installiert
- Memory und Logs schreibbar

Die fehlenden Codex-/OpenCode-Programme sind keine Profil- oder
Vault-Abweichung. Codex bleibt als benötigter BIZ-Builder-/Heavy-Duty-Harness
offen; OpenCode wird nur bei einem konkreten Bedarf installiert.

Die private Mac-Trinity verwendet nach erneuter Prüfung einen anderen,
erreichbaren Telegram-Bot: `Trinity_M5_bot`, Fingerprint `-roZaf1bcMsO`.
Damit sind die Telegram-Zugänge technisch getrennt. Es wurde keine
Testnachricht gesendet.

## Behobene Architekturabweichung

Die frühere Windows-Konfiguration zeigte trotz Profil `BIZ` noch auf einen
historischen Ordner `BrainVault`. Die T0-Nachprüfung bestätigt, dass diese
Abweichung inzwischen behoben ist:

- Root:
  `C:\Users\matmax\OneDrive - Hochschule für Wirtschaft und Umwelt\BizVault`
- Profil: `BIZ`
- zehn vorhandene Hauptordner plus `README.md`
- keine fehlenden oder unklassifizierten Einträge

Eine erneute Vault-Initialisierung ist nicht erforderlich.

## RAG-Nacharbeit

Der aktive Windows-RAG-Index verweist auf zurückgesetzte Testtranskripte, deren
Originale nur noch in Recovery liegen. Er darf nicht als produktiver BIZ-Index
weiterverwendet werden. Vor einer Neuerstellung sind ausschließlich bestätigte
berufliche Originalquellen aus dem BizVault auszuwählen. Recovery bleibt bis
zur geprüften Neuerstellung unangetastet.

## Noch ausstehende Sicherung

Der Ergebnisbericht nennt keine unabhängige verschlüsselte Kopie der lokalen
Windows-Installation, Runtime und Recovery auf `BACKUP_M5`. Solange kein
geprüfter Windows-Sicherungspfad dokumentiert ist, bleibt dieser Teil der
Phase-2-Backupregel offen. Das Mac-Sparsebundle darf dafür nicht verändert
werden.

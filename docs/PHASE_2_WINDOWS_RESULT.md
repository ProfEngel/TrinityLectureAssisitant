# Phase 2 – Windows-Ergebnis und kontrollierte Nacharbeit

Stand: 22. Juli 2026

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

Die private Mac-Trinity verwendet nach erneuter Prüfung einen anderen,
erreichbaren Telegram-Bot: `Trinity_M5_bot`, Fingerprint `-roZaf1bcMsO`.
Damit sind die Telegram-Zugänge technisch getrennt. Es wurde keine
Testnachricht gesendet.

## Verbliebene Architekturabweichung

Die Windows-Konfiguration zeigt trotz Profil `BIZ` noch auf einen Ordner
`BrainVault`. Ursache war ein inzwischen korrigierter alter Windows-Fallback im
Trinity-Code. Neue BIZ-Installationen schlagen OneDrive/`BizVault` vor.
Bestehende Konfigurationen werden aus Sicherheitsgründen nicht automatisch
umgeschrieben.

Auf Windows muss Trinity beendet und anschließend genau der bereits geprüfte
BizVault übernommen werden:

```powershell
$Trinity = "$env:LOCALAPPDATA\Trinity"
$BizVault = Join-Path $env:OneDriveCommercial "BizVault"
& "$Trinity\venv\Scripts\trinity.exe" --home $Trinity vault init `
  --profile BIZ `
  --root $BizVault `
  --accept-existing
& "$Trinity\venv\Scripts\trinity.exe" --home $Trinity vault status
```

Der Status muss danach `profile: BIZ`, den vorhandenen OneDrive-BizVault und
keine fehlenden Hauptordner melden. Der Befehl ergänzt nur fehlende
Strukturordner; vorhandene Inhalte werden nicht verschoben oder überschrieben.

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

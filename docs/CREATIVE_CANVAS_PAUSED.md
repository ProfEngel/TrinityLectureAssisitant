# Creative Canvas pausiert – 22.09.2026

TrinityHUB ist die separat betriebene Agentenoberfläche. Creative Canvas ist
nicht mehr Teil des normalen Desktop-Betriebs:

- kein Autostart, auch nicht mit einem alten `canvas.enabled: true`;
- kein Canvas-Reiter und keine Canvas-Statuskarte;
- kein Download/Build durch macOS-/Windows-Installer oder Desktop-CI;
- neue Konfigurationen deaktivieren Canvas standardmäßig.

Quellcode, Git-Submodule-Verweis und bestehende Canvas-Daten bleiben zur späteren
Wiederaufnahme erhalten. Die alten ausdrücklich aufgerufenen `trinity canvas`
Wartungsbefehle bleiben verfügbar; sie sind kein Teil des normalen Startwegs.
Kein Repository wird gelöscht oder schreibgeschützt archiviert. HUB wird dadurch
weder neu installiert noch umkonfiguriert. Bestehende Nutzerkonfigurationen und
Sprachmodelle werden nicht migriert.

Die MiniTrinity verwendet auf macOS ein verzögert geöffnetes Qt-Popup statt des
nativen Tray-Kontextmenüs. Dies umgeht den in lokalen Absturzberichten gefundenen
`NSEvent clickCount`/`NSMenuTrackingSession`-Abbruch. Windows behält sein natives
Tray-Menü. Automatisierte Tests prüfen die verzögerte Ausführung; die konkrete
macOS-Menüinteraktion bleibt zusätzlich praktisch zu prüfen.

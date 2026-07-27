# Implementierungsplan: Trinity Voice Studio mit optionaler Eve-Mimik

Stand: 22. Juli 2026

Dieser Plan behandelt ausschließlich das neue, eigenständige **Trinity Voice
Studio**. Das Produkt soll ohne Trinity für Sprachsynthese, Podcast und
Videocast nutzbar sein. Eine spätere Trinity-Anbindung ist ein optionaler
Adapter und keine Voraussetzung für den Standalone-Betrieb.

## 1. Produktentscheidung

### Eigenes privates Projekt

- Empfohlenes Repository: `ProfEngel/TrinityVoice`
- Sichtbarer Produktname: **Trinity Voice Studio**
- Empfohlene Arbeitskopie: `/Users/matmax/TrinityVoice`
- Eigenständige Anwendung mit eigenem Installer, Doctor, Update und Rollback.
- Keine Quellcodekopie im Trinity-Core-Repository.

### Sprachkern: Voicebox.sh bevorzugt prüfen

Voicebox ist bereits ein lokales, MIT-lizenziertes Voice-Studio mit Qwen3-TTS,
Voice Cloning, MLX/Metal auf Apple Silicon, REST, MCP, Stories-Editor und
Audioeffekten. Deshalb wird die Sprachtechnik nicht vorschnell neu gebaut.

Bevorzugte Architektur:

1. Die unveränderte Voicebox-Anwendung beziehungsweise ihr lokaler Backend-
   Dienst übernimmt Voice Cloning und Sprachsynthese.
2. Das neue Repository `TrinityVoice` ergänzt Eve, verständliche Abläufe,
   Medienproduktion, Datenschutzregeln und optionale Trinity-Adapter.
3. Ein Voicebox-Fork wird nur angelegt, wenn ein klar dokumentierter Bedarf
   nicht über die öffentliche REST- oder MCP-Schnittstelle lösbar ist.

Voicebox läuft lokal standardmäßig auf Loopback. Seine Remote-Schnittstelle hat
derzeit keine echte Authentifizierung. Sie darf deshalb nicht direkt ins LAN,
Tailnet oder Internet freigegeben werden. Das Feld `X-Voicebox-Client-Id` ist
eine Client-Zuordnung, kein Geheimnis und kein Zugriffsschutz.

### Mimik: Kling LivePortrait gezielt einsetzen

Der korrekte Projektname ist **Kling LivePortrait**. Die offizielle Version
unterstützt Menschenportraits auf Apple Silicon und kann ein Eve-Bild anhand
eines Fahrvideos oder eines gespeicherten Bewegungstemplates animieren.

Wichtig: LivePortrait ist kein reines Audio-zu-Lippenbewegungssystem. Ein
Tonfile allein erzeugt keine belastbare Lippensynchronität. Dafür wird entweder
ein zusätzliches Audio-zu-Bewegungsmodul, ein passend erzeugtes Fahrvideo oder
ein späterer Render-Schritt benötigt. Außerdem weist das Projekt darauf hin,
dass die Apple-Silicon-Ausführung deutlich langsamer als eine RTX 4090 sein
kann. Echtzeit wird deshalb nicht versprochen, sondern gemessen.

### Technische Originalquellen

- Voicebox: <https://github.com/jamiepine/voicebox>
- Voicebox-Dokumentation: <https://docs.voicebox.sh/>
- Kling LivePortrait: <https://github.com/KlingAIResearch/LivePortrait>
- Qwen3-TTS: <https://github.com/QwenLM/Qwen3-TTS>

Die Versionen und Lizenzen müssen zu Beginn der Umsetzung erneut geprüft und im
neuen Repository festgehalten werden.

## 2. Verbindliche Grenzen

- Voice Studio liest weder BrainVault noch BizVault automatisch.
- Voice Studio besitzt kein Trinity-Memory und keinen RAG-Zugriff.
- Stimme, Eve-Bild, Fahrvideos und generierte Medien werden nie in Git committed.
- Voicebox-Personality-Rewrite bleibt bei Trinity-Aufrufen ausgeschaltet:
  Trinity formuliert die Antwort, Voice Studio spricht sie nur.
- Die erste Trinity-Freigabe gilt ausschließlich für **Privat/PRIVAT auf dem
  M5**.
- BIZ-Text darf nicht automatisch vom Windows-System an den privaten Mac gehen.
- Avatar und Mimik bleiben optional und vollständig abschaltbar.
- Standalone-Sprachausgabe funktioniert auch ohne Avatar.
- Trinity funktioniert auch ohne Voice Studio.

## 3. Abnahmeregeln

Jede Phase endet mit einer Entscheidung: freigeben, überarbeiten oder verwerfen.

- Persönliche Medien und Secrets erscheinen weder in Git noch in Logs.
- Modelle und große Laufzeitdaten liegen lokal außerhalb von Cloud-Vaults.
- temporäre Medien besitzen verständliche Lösch- und Aufbewahrungsregeln.
- Installieren, Aktualisieren, Zurücksetzen und Entfernen sind testbar.
- fremde Projekte werden möglichst als unveränderte Abhängigkeiten verwendet.
- Performance wird auf dem tatsächlichen M5 gemessen, nicht geschätzt.
- kein Release ohne reproduzierbaren Test und verständliche Release Notes.

## V0 – Rechte, Medien und Qualitätsziel festlegen

### Benötigte Eingaben

- sauberer Stimmtest als WAV, zunächst etwa 10 bis 30 Sekunden;
- wortgetreues Transkript;
- Bestätigung, dass die Stimme geklont und verwendet werden darf;
- hochauflösendes Eve-Bild: frontal, gleichmäßig beleuchtet, Gesicht frei;
- gewünschte Einsatzarten: Live-Antwort, Podcast und Videocast;
- gewünschte Stile: vertraut, sachlich, warm, amüsiert, ernst und freundlich-
  schnippisch.

### Arbeiten

- private Originale und lokale Arbeitskopien klar trennen.
- Aufbewahrung und Löschung der Voicebox-Generationen festlegen.
- feste deutsche Vergleichstexte bestimmen.
- Qualitätskriterien für Stimme, Latenz, Mimik und Lippensynchronität definieren.
- Voice Cloning zuerst; Fine-Tuning nur nach nachgewiesenem Bedarf.

### Abnahme

- Rechte, Speicherorte und Testkriterien sind bestätigt.
- Keine Installation und kein Repository vor dieser Bestätigung.

## V1 – Voicebox auf dem M5 technisch und klanglich prüfen

### Ziel

Feststellen, ob Voicebox den Sprachkern bereits zuverlässig liefert.

### Arbeiten

- offizielle Apple-Silicon-Version isoliert installieren.
- Datenpfad und Modellcache dokumentieren.
- Qwen3-TTS 0.6B und 1.7B mit derselben Eve-Stimmprobe vergleichen.
- Deutsch, Zahlen, Namen, Abkürzungen und englische Fachbegriffe testen.
- Startzeit, Zeit bis zum ersten Ton, Echtzeitfaktor, Speicher und Temperatur
  messen.
- REST-Endpunkte für Profil, Erzeugung, Status und Audiodatei prüfen.
- prüfen, welche erzeugten Audiodateien Voicebox dauerhaft aufbewahrt.
- Personality-Funktion für spätere Trinity-Aufrufe deaktiviert lassen.

### Abnahme

- ausgewähltes Modell klingt auf Deutsch überzeugend und konsistent;
- Voicebox läuft auf dem M5 stabil;
- lokaler API-Ablauf ist dokumentiert;
- Entscheidung: unverändert verwenden, Adapter ergänzen oder begründet forken.

## V2 – Eigenes privates Standalone-Repository anlegen

### Ziel

Ein eigenes Produkt entsteht, ohne Voicebox oder LivePortrait unkontrolliert zu
kopieren.

### Arbeiten

- privates Repository `ProfEngel/TrinityVoice` anlegen.
- lokale Arbeitskopie `/Users/matmax/TrinityVoice` erstellen.
- verständliche Struktur einrichten:
  - `app/` für Standalone-Oberfläche und Orchestrierung,
  - `voice/` für den Voicebox-Adapter,
  - `eve/` für LivePortrait und Bewegungsabläufe,
  - `media/` für Podcast- und Videocast-Verarbeitung,
  - `tests/` und `docs/`.
- private Medien, Modelle, Cache, Generierungen und Konfiguration ignorieren.
- Lizenz- und Herkunftsübersicht aller Abhängigkeiten anlegen.
- Doctor, Version und lokale Health-Prüfung vorbereiten.

### Abnahme

- frischer Clone enthält keine persönlichen oder großen Binärdaten;
- Anwendung startet auch bei noch fehlendem Avatar;
- fehlendes Voicebox oder LivePortrait wird verständlich erklärt;
- Repository besitzt keine technische Pflichtabhängigkeit zu Trinity.

## V3 – Standalone-Sprachstudio fertigstellen

### Ziel

Texte lassen sich unabhängig von Trinity sprechen, prüfen und exportieren.

### Arbeiten

- Voicebox-Profile anzeigen und Eve eindeutig auswählen.
- Text schreiben, einfügen oder als Markdown importieren.
- Stil, Sprache, Geschwindigkeit und Voicebox-Engine wählen.
- kurze Vorschau vor vollständigem Rendern ermöglichen.
- lange Texte an Satz- und Abschnittsgrenzen verarbeiten.
- Streaming-Wiedergabe, Abbruch und erneuten Start unterstützen.
- WAV-Ausgabe und komprimierte Hörprobe anbieten.
- Generationen behalten, gezielt löschen oder automatisch aufräumen können.
- Voicebox-Fehler in verständliche Meldungen übersetzen.

### Abnahme

- Standalone-Betrieb ohne Trinity erfolgreich;
- lange deutsche Texte ohne vertauschte oder doppelte Abschnitte;
- laufende Wiedergabe zuverlässig abbrechbar;
- gespeicherte und temporäre Ausgaben eindeutig unterscheidbar.

## V4 – Kling LivePortrait als eigenständiges Eve-Modul prüfen

### Ziel

Ein Eve-Bild wird reproduzierbar mit kontrollierter Mimik animiert.

### Arbeiten

- LivePortrait in einer getrennten Python-Umgebung installieren.
- Menschenmodus auf dem M5 prüfen; Tiermodus bleibt außerhalb des Umfangs.
- Eve-Original unverändert sichern und nur Arbeitskopien verwenden.
- kurze eigene Fahrvideos für neutral, zuhören, denken, lächeln, skeptisch und
  freundlich-schnippisch erstellen.
- aus den Fahrvideos datensparsame Bewegungstemplates erzeugen.
- Qualität von Gesicht, Augen, Mund, Haaren und Kopfbewegung prüfen.
- Renderzeit, Speicher und Temperatur pro Zielauflösung messen.
- LivePortrait als austauschbaren Adapter kapseln.

### Abnahme

- mindestens sechs stabile Eve-Zustände sind reproduzierbar;
- keine unvertretbaren Identitäts- oder Gesichtsartefakte;
- klare Entscheidung, welche Auflösung und Bildrate der M5 sinnvoll schafft;
- keine Behauptung von Echtzeit ohne bestandenen Echtzeittest.

## V5 – Sprache, Mimik und Lippensynchronität verbinden

### Ziel

Voicebox-Audio und Eve-Bild ergeben einen glaubwürdigen sprechenden Auftritt.

### Drei getrennte Stufen

1. **Sofortmodus:** Während Voicebox spricht, zeigt Eve einen passenden
   LivePortrait-Zustand. Das ist stabil, aber nicht exakt lippensynchron.
2. **Rendermodus:** Fertiges Audio wird mit einem zusätzlichen Audio-zu-Mund-
   beziehungsweise Lip-Sync-Schritt zu einem Videoclip verarbeitet.
3. **Echtzeitmodus:** Nur bei erfolgreichem M5-Benchmark; andernfalls bleibt er
   experimentell oder wird später auf einen ausdrücklich freigegebenen Server
   ausgelagert.

### Arbeiten

- Audiozeit, Satzgrenzen und emotionale Zustände als gemeinsame Zeitleiste
  definieren.
- LivePortrait-Zustände passend wechseln und weich überblenden.
- für Rendermodus geeignete Lip-Sync-Komponenten separat evaluieren.
- erkennen, dass LivePortrait allein keine Audio-Lippensynchronität liefert.
- Abbruch und Neuanfang ohne alte Audio- oder Videofragmente sicherstellen.
- künstlich erzeugte Videos auf Wunsch sichtbar kennzeichnen.

### Abnahme

- Sofortmodus ist stabil und jederzeit abschaltbar;
- Rendermodus erreicht akzeptierte Lippenbewegung und Identitätstreue;
- Echtzeit wird nur nach tatsächlicher Messung als produktiv bezeichnet.

## V6 – Podcast- und Videocast-Werkstatt

### Ziel

Trinity Voice Studio produziert längere Medien unabhängig von Trinity.

### Arbeiten

- Skript als Text oder Markdown einlesen.
- Rollen, Pausen, Aussprache und Stil pro Passage erlauben.
- einzelne Absätze vorhören und nur geänderte Teile neu rendern.
- Kapitel verlustfrei zusammensetzen.
- Lautheit und Übergänge vereinheitlichen.
- WAV, Kapiteldateien und Produktionsprotokoll exportieren.
- optional Eve-Video pro Abschnitt rendern und zu einem Videocast verbinden.
- Modell, Stimme, Einstellungen und Prüfsummen protokollieren.

### Abnahme

- mehrseitiges deutsches Skript abschnittsweise korrigierbar;
- unveränderte Kapitel werden nicht erneut berechnet;
- Podcast besitzt gleichmäßige Lautheit und saubere Übergänge;
- Videocast kann unabhängig von einer Live-Session erzeugt werden.

## V7 – Trinity nur als optionalen Client anbinden

### Ziel

Private Trinity-Antworten können gesprochen und optional animiert werden, ohne
Voice Studio zum Teil des Trinity-Cores zu machen.

### Arbeiten

- kleinen versionierten Adapter definieren: Text, Sprache, Stil, Request-ID,
  Session-ID und Profil.
- Trinity verbindet sich nicht direkt mit der ungeschützten Voicebox-API,
  sondern mit einem lokalen Trinity-Voice-Gateway.
- Gateway prüft Token und erwartetes Profil und bindet intern nur an Loopback.
- Voicebox-Aufruf mit `personality: false`, damit nichts umformuliert wird.
- Systemstimme als Rückfalllösung behalten.
- Status an Trinity melden: lädt, bereit, spricht, rendert, abgebrochen, Fehler.
- Voice Studio in Doctor aufnehmen, aber nicht zwingend voraussetzen.

### Abnahme

- Voice Studio ausgeschaltet: Trinity funktioniert unverändert;
- eingeschaltet: private Antworten werden in derselben Request-Reihenfolge
  gesprochen;
- falsches Profil oder Token wird abgewiesen;
- Fehler führen zur Systemstimme und nicht zum Trinity-Ausfall;
- BIZ wird nicht an den privaten Mac weitergeleitet.

## V8 – Companion- und Netzwerkbetrieb kontrolliert ergänzen

### Ziel

iPhone und iPad empfangen Ton und optional Eve, ohne Voicebox selbst nach außen
zu öffnen.

### Arbeiten

- Ton über die bereits profilgesicherte Trinity-Verbindung übertragen.
- kleine lokale Eve-Zustandsanimationen für Companion bevorzugen.
- große Videos nur auf ausdrücklichen Abruf übertragen.
- aktive Profilkennzeichnung immer sichtbar halten.
- Rückfall bei schwacher Verbindung und Stromsparmodus vorsehen.
- Voicebox-Port niemals direkt im Companion konfigurieren.
- Remote-Voicebox nur später hinter VPN und echter Gateway-Authentifizierung
  prüfen.

### Abnahme

- Ton funktioniert bei deaktiviertem Avatar;
- Avatar verdeckt weder Profil noch Bedienung;
- schwache Verbindung beeinträchtigt den Chat nicht;
- kein ungeschützter Voicebox-Endpunkt ist im Netz erreichbar.

## V9 – Installation, Release und dauerhafte Pflege

### Ziel

Voice Studio lässt sich eigenständig installieren, aktualisieren und entfernen.

### Arbeiten

- macOS-Anwendung und verständlichen Erststart erstellen.
- Voicebox und LivePortrait erkennen, installieren oder getrennt reparieren.
- Modelldownload mit Größe, Ziel und Fortschritt anzeigen.
- vorhandene private Medien erkennen und niemals überschreiben.
- Update mit Konfigurationssicherung und Rollback bauen.
- Deinstallation von Runtime und Modellen anbieten; Originalmedien nur nach
  gesonderter Bestätigung löschen.
- Release Notes, Datenschutz, verantwortliche Nutzung und Lizenzen beilegen.
- Kompatibilitätsmatrix für Voicebox, LivePortrait und Trinity führen.

### Abschlussabnahme

- Standalone-Stimme und Medienwerkstatt funktionieren ohne Trinity;
- optionale Trinity-Anbindung funktioniert für Privat;
- Podcast-Export ist stabil;
- Eve bleibt optional und vollständig deaktivierbar;
- keine persönlichen Medien gelangen unbemerkt in Git, Logs oder ein falsches
  Profil;
- Installation, Update, Rollback und Entfernung sind geprüft.

## 4. Was nicht automatisch geschehen darf

- kein Voicebox-Fork ohne dokumentierte Lücke der öffentlichen Schnittstelle;
- keine direkte Änderung im installierten Voicebox- oder LivePortrait-Code;
- kein Zugriff auf BrainVault, BizVault, Trinity-Memory oder RAG;
- keine Veröffentlichung der Stimme, des Eve-Bildes oder der Fahrvideos;
- kein Fine-Tuning vor der Voice-Cloning-Abnahme;
- kein Versprechen fotorealistischer M5-Echtzeit vor einem Benchmark;
- keine BIZ-Übermittlung an den privaten M5;
- keine Avatarpflicht und keine Android-App.

## 5. Startauftrag für einen neuen Codex-Chat

> Wir beginnen das neue private Projekt **Trinity Voice Studio** anhand von
> `/Users/matmax/Trinity_Assistant/docs/IMPLEMENTIERUNGSPLAN_TRINITY_VOICE_STUDIO.md`.
> Lies den Plan vollständig und prüfe die dort verlinkten offiziellen Quellen
> von Voicebox, Kling LivePortrait und Qwen3-TTS auf ihren aktuellen Stand.
> Beginne ausschließlich mit **V0**. Lege noch kein Repository an, installiere
> keine Modelle und verändere Trinity nicht, bevor Rechte, private Speicherorte,
> Aufbewahrung, Testtexte und Qualitätskriterien dokumentiert und von mir
> bestätigt wurden. Ziel ist eine eigenständige Anwendung. Voicebox soll
> bevorzugt unverändert als lokaler Sprachkern über seine API verwendet werden;
> ein Fork benötigt eine belegte technische Begründung. Kling LivePortrait
> erzeugt Mimik aus Fahrvideos oder Bewegungstemplates und darf nicht als
> vollständiges Audio-Lip-Sync-System vorausgesetzt werden. Die erste spätere
> Trinity-Freigabe gilt nur für Privat/PRIVAT auf dem M5.

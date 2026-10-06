# DeckUI – private Klangbibliothek

DeckUI ist eine Fernsteuerung für kurze Einspieler und vorhandene MP3s. Die
Companion-App zeigt eine native Kachelansicht auf iPad und iPhone; `/deck`
liefert zusätzlich eine WebUI. Jede Kachel hat einen eindeutigen Einwortnamen.

## Bedienung

- Tippen startet den Klang; nochmaliges Tippen auf dieselbe Kachel stoppt ihn.
- Eine andere Kachel ersetzt den laufenden Deck-Klang, ohne mehrere Einspieler
  zu stapeln. Die Stopptaste beendet den Deck-Klang.
- „Trinity, NAME!“ bzw. „Trinity, spiele NAME!“ löst dieselbe Steuerung direkt
  aus. „Trinity, Deck stoppen!“ stoppt. Kein LLM-, Musik- oder Bildjob wird
  dafür angelegt. Wörter innerhalb normaler Sätze sind keine Auslöser.
- Ausgabe ist **nur auf dem ausgewählten Trinity-Ausgabegerät**. Bei dessen
  Wechsel wird der Einspieler gestoppt, nicht auf beiden Geräten fortgesetzt.
- Bei Lautsprecherwiedergabe verhindert der vorhandene Echoschutz, dass der
  Einspieler als Nutzerstimme transkribiert wird. Zum Stoppen währenddessen
  die Kachel nutzen; Sprachunterbrechung setzt eine geeignete Kopfhörerroute
  bzw. den ausdrücklich aktivierten Mac-Kopfhörermodus voraus.

## Private Installation

Eine eigene, nicht im Repository gespeicherte JSON-Datei beschreibt nur die
ausdrücklich ausgewählten MP3s:

```json
{"sounds": [{"id": "jubel", "name": "Jubel", "icon": "hands.clap.fill", "source": "/private/audio/cheering.mp3"}]}
```

```sh
python tools/import_sound_deck.py --home SERVER_HOME --manifest PRIVATE_JSON
```

FFmpeg/ffprobe werden zum Import benötigt, nicht zum Abspielen in iOS. Der
Importer kopiert die MP3s, prüft die Dauer und erzeugt eine Mono-24-kHz-WAV
für den Desktop-Mixer. Dateien, manifest.json und die kleine Steuerdatenbank
liegen ausschließlich unter dem ignorierten `TrinityRuntime/sounddeck/`.
Die Quelldateien werden nicht geändert. Keine privaten Audiodateien gehören
in Quellcodearchive, App-Bundles oder öffentliche Releases.

## Architektur / Sicherheitsgrenzen

Die Bridge stellt authentifizierte `/deck/catalog`, `/deck/state`,
`/deck/audio/ID`, `/deck/pcm/ID` und POST `/deck/toggle`, `/deck/stop`,
`/deck/ack` bereit. Bibliothek und Steuerung sind nur Instanzbetreibern
zugänglich. Die öffentliche WebUI enthält weder Bibliothek noch Token.

SQLite serialisiert Start/Stop aus mehreren Prozessen. Jede Änderung erhält
eine neue Revision: verspätete Downloads und Fertigmeldungen können keinen
nachfolgenden Klang stoppen. Der eine Realtime-Router verteilt `trinity.deck`
an die verbundenen Ein-/Ausgabegeräte. Ausschließlich der aktuelle Ausgang
spielt ab und bestätigt echte Wiedergabe alle zwei Sekunden. Ohne Bestätigung
läuft die Startanforderung nach 15 Sekunden aus; eine ausgefallene Wiedergabe
nach sechs Sekunden. Es gibt keine zusätzlichen STT-/TTS-/LLM-Instanzen.

Der Mac mischt begrenztes, vorab dekodiertes PCM im bestehenden Audiostream,
einschließlich BlackHole-Ausgabe. iOS verwendet AVAudioPlayer ohne eine zweite
Audio-Session; der aktivierte iPad-Hörsaalmodus verwendet stattdessen dessen
Sound-Bus. Wiedergabe bleibt außerhalb der Talk-Medienergebnisliste.

Die WebUI steuert die ausgewählte native App, nicht den Browserlautsprecher:
Die App muss verbunden sein und die DeckUI-Version unterstützen. Somit gibt
es auf iOS keine Abhängigkeit von HTML-Autoplay-Berechtigungen.

## Abnahme

1. Kurzen Klang tippen, natürliches Ende und erlöschende Markierung prüfen.
2. Langen Klang tippen, erneut tippen: sofortiger Stopp.
3. Während eines Klangs eine andere Kachel tippen: nur der neue Klang läuft.
4. „Trinity, NAME!“ außerhalb der Deck-Ansicht sagen: derselbe Klang läuft.
5. Ausgabegerät wechseln: altes Gerät stoppt; neuer Tastendruck spielt nur auf
   dem neuen Gerät. Es entsteht kein doppelter Einspieler.
6. Netzwerkverlust und Serverneustart: kein automatisches Wiederabspielen;
   nach Wiederverbindung neuer, bewusster Start.
7. iPad-Hörsaalmodus: Pegel am Sound-Regler und bestätigte HDMI-Route prüfen.
   USB/HDMI-Hardwaretests sind zusätzlich erforderlich, keine Simulation
   bestätigt die physische Route.

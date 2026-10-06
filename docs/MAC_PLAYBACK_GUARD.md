# Mac-Lautsprecherschutz · 2026-10-06

Nur Desktop-Client-Code; keine Änderung an Linux-Modellen, Eve-Stimme oder
Companion-App. Der eingefrorene GitHub-Release bleibt unverändert.

## Verhalten

- Auf macOS ist Reinsprechen während einer Antwort standardmäßig aus. Der
  Server erhält während lokaler Wiedergabe keine Mikrofon-/Systemtonpakete,
  die Eve erneut als Benutzerrede erkennen könnten.
- Ende bedeutet: Empfangspuffer leer, keine offene Audiogenerierung, Hardware-
  Ausgabepuffer abgespielt und 350 ms Echo-Nachlauf. `response.done` allein
  gibt das Mikrofon nicht frei. Bei einer fehlenden Abschlussnachricht ist die
  zusätzliche Wartezeit auf weitere Audiopakete auf 15 Sekunden begrenzt.
- Erzeugte PCM-Daten, Samplerate, Eve-Referenz und Abspielgeschwindigkeit sind
  unverändert. Das virtuelle Mikrofon für Teams/OBS bleibt ebenfalls erhalten.
- **Antwort stoppen** beendet nur die aktuelle Mac-Ausgabe, ohne dauerhaft
  stummzuschalten. Der Besitzer wird beim Klick und bei Ausführung erneut
  geprüft: ein zwischenzeitlich gewähltes iPad/iPhone wird nicht gestoppt.
- **Unterbrechen durch Reinsprechen (Kopfhörer)** ist optional und gespeichert.
  Nur mit Kopfhörern aktivieren; der bisherige korrelationsbasierte Echoschutz
  ist keine Garantie gegen Lautsprecherechos. Bei ausgeschaltetem Modus kann
  ein gesprochener Stopp während TTS nicht gehört werden: Menü/G2-Stopp nutzen.
- Wenn der Mac Mikrofon, aber ein anderes Gerät Lautsprecher ist, respektiert
  nur der Mac-Eingang die vorhandenen Server-Ausgabeaktivitätsmeldungen. Die
  mobilen Player und der zentrale Gerätebesitz werden nicht verändert.
- Debug meldet Mikrofonpause/-freigabe und Ursache eines Audioabbruchs. Keine
  Terminal-/Dateizugriffe im CoreAudio-Callback.

## Feldtest

1. MiniTrinity: Mac zuhören und Mac antworten; Kopfhörer-Reinsprechen **aus**.
2. „Trinity, erkläre Korrelation und Kausalität in vier kurzen Sätzen.“ Während
   der Antwort schweigen. Alle Sätze müssen hörbar sein, Debug zeigt die
   Mikrofonpause und anschließend die erneute Freigabe.
3. Aktives Textfenster öffnen: „Trinity, lies den sichtbaren Text vor.“ Ganze
   Wiedergabe prüfen. Dies testet Audio, nicht wortgetreue OCR-Qualität.
4. Längere Antwort mit **Antwort stoppen** abbrechen, danach erneut fragen.
5. iPad/iPhone als Ausgabe wählen; normales Gespräch prüfen. Mac darf weder
   Audio doppelt spielen noch eine mobile Antwort abbrechen.
6. Optional Kopfhörer verwenden, Reinsprechen einschalten und unterbrechen.
   Danach bei Lautsprecherbetrieb die Option wieder ausschalten.

Ein Raum-/Lautsprechertest muss am echten Mac durchgeführt werden. Automatische
Tests prüfen PCM-Erhalt, Pufferende, DAC-/Echo-Nachlauf, Satzlücken, Abbruch,
Kopfhörermodus und Geräteübergabe; sie ersetzen keine akustische Abnahme.

# Satz-Streaming — Entwicklungsstand 2026-10-02

Auf Linux aktiviert; noch keine akustische/langfristige Abnahme am Endgerät.
Schalter: `system.voice_sentence_streaming` in der vorhandenen Laufzeitkonfiguration.
Bei `false` bleibt der bisherige vollständige Antwortpfad verfügbar.
Quell-Backups: `/home/your-user/TrinityRuntime-stream-test-CBBDR1/`.
Konfiguration vor Aktivierung ebenfalls gesichert. Keine Schlüssel, Voice-
Referenzen oder Memory-Daten überschrieben. Kein Client-App-Update erforderlich.

Der Voice-HTTP-Pfad konsumiert sichtbare OpenAI-SSE-Inhalte inkrementell.
Der Brain behält Router, Bildkontext und Memory-Retrieval; Reasoning-Felder
werden nicht als Antwort verwendet. Vollständig abgeschlossene Antworten
werden einmal in das bestehende Memory geschrieben. Fehler/Abbrüche werden
nicht durch einen nachträglich gespeicherten Ersatztext verschleiert.

Eine begrenzte Queue mit acht Einträgen verbindet Brain und HTTP-Verbindung.
Verbindungsabbruch und neuere Fragen verwerfen weitere Sätze. Ein blockierter
Netzwerk-Read kann trotzdem bis zum bestehenden Read-Timeout dauern.

Die vorhandene Zwei-Satz-TTS-Bündelung und Eve-Klonprüfung bleiben unverändert.
Das allein garantiert keine lückenlose oder prosodisch durchgängige Sprache.
Für die vollständige Abnahme sind echte Eve-Messungen erforderlich: erste Audio-Latenz,
Übergangspausen, Synthese schneller als Wiedergabe, Gerätewechsel, Abbruch,
Vision, Agenten und mindestens 20 Minuten Dialog. Client-Audio-Pufferung und
die Upstream-TTS-Queue müssen auf dem Server zusätzlich geprüft werden.

## Durchgeführte Prüfungen

UTF-8-Korrektur: requests behandelte SSE ohne charset als ISO-8859-1; dadurch
erhielt Eve z. B. `fÃ¼r` statt `für`. Der eingehende SSE-Decoder verwendet nun
explizit UTF-8; der ausgehende Stream nennt ebenfalls `charset=utf-8`.
Regression mit echten UTF-8-Bytes, Latin-1-HTTP-Default und 1-Byte-Chunks
reproduziert den Fehler vorher und besteht nach der Korrektur. 110 Tests
erfolgreich. Auf Linux nach Quell-Backup aktiviert; bestehende gespeicherte
Antworten wurden nicht rückwirkend umgeschrieben.

- 109 lokale Voice-/Brain-Prompt-Tests erfolgreich, einschließlich HTTP-SSE
  vor Generierungsende, einmaligem vollständigem Memory-Schreiben und Abbruch
  ohne persistierten Ersatztext.
- Echter sichtbarer Modellstream: erster Satz 2,95 s, Abschluss 5,29 s.
- Stille Eve-Probe derselben längeren Frage: vorher erster Audio-Puffer
  12,01 s; mit Streaming 6,52 und 6,55 s. Das sind Einzelmessungen,
  keine allgemeine Latenzgarantie. Die Antworten waren unterschiedlich lang.
- Bei beiden Streaming-Proben kein berechnetes Playout-Unterlaufen >150 ms.
  Das prüft Paketankunft gegen empfangene PCM-Dauer, nicht Prosodie, HDMI,
  Funkstrecke oder hörbare Satzübergänge am Gerät.
- Eve-Referenz, Validierung und Zwei-Satz-TTS-Batching unverändert.
- Server nach Neustart aktiv; Ports 8765, 8766 und intern 18766 erreichbar.
  GPU 17.648 / 20.470 MiB, kein zweites STT/LLM/TTS-Modell gestartet.

Noch erforderlich: 20 Minuten echter Dialog, hörbare Übergänge, Abbruch und
Gerätewechsel während laufender Ausgabe, besonders bei Vision und Agenten.

Automatisiert belegt: Erster SSE-Satz erreicht den Client, während die
Generierung des zweiten absichtlich noch blockiert ist. Keine Aussage über
physische Audioausgabe oder Produktions-Latenz.

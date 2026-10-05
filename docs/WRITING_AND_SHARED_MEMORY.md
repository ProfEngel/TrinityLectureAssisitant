# Gemeinsames Memory und Schreiben per Sprache – 2026-10-01

Trinity verwendet eine gemeinsame serverseitige Unterhaltung. Technische
Session-IDs dienen der Ablage, nicht der Auswahl getrennter Erinnerungen.
Ein automatischer Tageswechsel ist noch nicht implementiert. Alte Clients
können `/session/close` weiterhin aufrufen; der Server bestätigt dies ohne
Aufteilung der Unterhaltung und ohne automatische Zusammenfassung. Alte
`/session/end`-Aufrufe erstellen ebenfalls keine automatische Zusammenfassung.
Eine explizite administrative Zusammenfassung bleibt mit `explicit_summary`
verfügbar. Manuell angeforderte Textzusammenfassungen bleiben selbstverständlich
erhalten.

Die vorgeschaltete Sprachpipeline bewahrt höchstens sechs Transport-Turns und
verwirft ältere Transport-Einträge, statt das LLM erneut zur internen
Verlaufskompression aufzurufen. Trinitys eigenes Langzeit-Memory bleibt erhalten.
Bereits gespeicherte interne Kompressionsanfragen werden bei der Memory-Suche
ausgefiltert, nicht gelöscht. Auch ein Diktat-Start/Stop oder eine neue
Lecture-Äußerung entwertet inzwischen eine noch laufende ältere Antwort.

## Schreiben auf dem Mac

Das Schreibziel ist das aktive zugängliche Textfeld. Der native Helfer unterstützt
AXTextArea und AXTextField mit auswählbarem Textbereich, nicht Passwortfelder.
Fenster, Feldidentität, Textbestand und bei Diktat die Cursorposition werden
geprüft. Anwendungen, die keinen solchen Zugriff anbieten, werden abgelehnt.
Die interne Benennung `textedit_*` bleibt aus Kompatibilitätsgründen bestehen;
sie bedeutet nicht mehr, dass ausschließlich TextEdit erlaubt ist.

- „Diktat starten“, „Diktat beenden“ / „Diktat Ende“.
- „Trinity, fasse das Diktat zusammen“: Vorschau darunter.
- „Trinity, überarbeite das Diktat“: Verbesserungsvorschlag darunter.
- „Trinity, ändere den Text: Schreibe den Satz über Modelle in Spiegelpunkten“:
  erneute Änderung des Vorschlags, beziehungsweise der Zusammenfassung.
- „Trinity, übernimm die neue Fassung“: geprüfter Ersatz des ursprünglichen Blocks.
- Eine explizite Textmarkierung hat Vorrang vor einem alten Diktatblock.
- „Trinity, schreibe unsere Gedanken zum Thema Transformer“: Gesprächsnotizen
  aus passenden Memory-/Verlaufsquellen an der Cursorposition.
- „Trinity, einfügen“: letzte Antwort an der Cursorposition; gegebenenfalls vorher
  „Trinity, Bearbeitung abschließen“, um einen gebundenen alten Block freizugeben.
- „Trinity, was kannst du hier beim Schreiben tun?“: Hilfe vorlesen.

Trinity darf am Anfang oder Ende eines einfachen Schreibbefehls stehen.
Explizite Überarbeitungsbefehle mit Wakeword beenden ein laufendes Diktat.
Ohne Wakeword bleiben diese Worte während eines Diktats wörtlicher Dokumenttext.
Die Zwischenablage wird nicht automatisch gelesen.

## App-Öffnen und erste Mailsteuerung

„Trinity, öffne …“ unterstützt Mail, Excel, Word, PowerPoint, Chrome, ChatGPT,
Finder, TextEdit, Safari und Outlook anhand fest vorgegebener Bundle-IDs.
Keine frei formulierten Shellbefehle werden ausgeführt.

Bei aktivem Apple Mail: „Trinity, nächste Mail“, „Trinity, vorherige Mail“
(Nachrichtenliste muss fokussiert sein), „Trinity, suche in Mail“,
„Trinity, neue Mail“, „Trinity, beantworte diese Mail“.
Diese Befehle lösen native Tastenkürzel aus. Ein geöffnetes Antwortfenster ist
noch keine gelesene und beantwortete Mail. Inhaltszugriff, Empfängerprüfung und
bestätigter Versand sind weitere, noch nicht implementierte Schritte.

## Prüfung

Zusammenfassung im echten Mac-Client an einem eigenen TextEdit-Testdokument
eingesetzt. Dafür wurden fertige STT-Ereignisse eingespeist, nicht das Mikrofon
getestet. 500 isolierte Turns mit der installierten Sprachpipeline geprüft:
sechs Transport-Turns erhalten, keine interne LLM-Kompression ausgelöst.
Dies ersetzt keinen 10–15-minütigen schnellen realen Sprechtest.

Companion 0.18.4 (aktuelles iCloud-Projekt): Session-Seitenleiste und Neuer-Session-Buttons entfernt,
iPhone-Bodenleiste mit fester Inhaltsgeometrie und Safe-Area-Inset repariert.
Vortragsmodule: Umbenennen und persistente Reihenfolge über „Nach oben/unten“.
Umbenennen überschreibt keinen bestehenden Ordner und erhält Folien/Notizen.
Auf iPhone und iPad installiert; iPhone-Layout im Simulator visuell geprüft.

## Exklusive Bildquelle

Die ausgewählte TTS-Ausgabe (`system.speech_output`) bestimmt allein die
Bildquelle, unabhängig vom STT-Eingang. Mac-Ausgabe erlaubt nur dessen
gezielte Fensteraufnahme; Companion-Ausgabe erlaubt nur dessen Folienkontext.
Client und Server prüfen die Zuordnung. Beim Lesen des Kontexts prüft der Server
zusätzlich, dass das Bild aus der aktuellen Ausgabe-Zuordnung stammt. Stumm
bedeutet keine Bildquelle. Alte Clients ohne Bild-Geräte-ID werden abgewiesen.
Getrennte Mikrofone, fremde/späte Uploads, Rückwechsel und Stumm wurden geprüft.
178 Tests erfolgreich; reale Gerätewechsel mit unterschiedlichen Bildinhalten
bleiben als Nutzertest offen.

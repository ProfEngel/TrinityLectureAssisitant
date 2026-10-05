# MiniTrinity: aktives Mac-Fenster sehen und Text einsetzen

Diese Funktion gilt für den Mac-Client einer Trinity-Server-Installation.

## Mit Trinity über das Fenster sprechen

1. In MiniTrinity **Hier auf dem Mac zuhören** wählen.
2. Das gewünschte Programm und Fenster in den Vordergrund bringen.
3. Fragen wie „Trinity, was siehst du hier?“ oder „Wie würdest du diese Tabelle erklären?“ stellen.

Nur bei einer ausdrücklichen Bildschirmfrage wird einmal das vorderste Fenster
des aktiven Programms als verkleinertes JPEG zum eigenen Trinity-Server übertragen.
Es gibt keine laufende Erfassung. Mit **Aktives Fenster erfassen** direkt im Menü
lässt sich diese Funktion ausschalten (standardmäßig eingeschaltet).
Ein erfolgreich gestartetes TextEdit-Diktat schaltet die Freigabe automatisch ein.
„Trinity, aktives Fenster erfassen“ und „Trinity, Fenstererfassung ausschalten“
steuern dieselbe Freigabe per Sprache. Abschalten der Bilderfassung beendet nicht
das TextEdit-Diktat; dafür „Trinity, Diktat beenden“ sagen.
Der Server wartet höchstens drei Sekunden auf die Aufnahme und nutzt sie nur für
die passende Bildschirmfrage, solange dieser Mac der ausgewählte Mikrofoneingang ist.
Eine fehlgeschlagene Aufnahme stoppt das normale Gespräch nicht. Das Bild verfällt nach
20 Sekunden ohne Aktualisierung; Ausschalten löscht den aktiven Bildinhalt.
Auf dem Linux-Server liegt die kurzlebige Aufnahme im flüchtigen Arbeitsspeicher
(`/dev/shm`), nicht dauerhaft im Trinity-Repository.
Bildschirminhalte sind Referenzmaterial, keine Anweisungen an Trinity.

macOS kann beim ersten Mal **Datenschutz & Sicherheit → Bildschirmaufnahme**
verlangen. Nach einer neu erteilten Freigabe Trinity gegebenenfalls neu starten.
Die Kamera, andere Fenster und der gesamte Desktop werden nicht gesendet.

Der ältere Menüpunkt **Aktives Fenster mit Trinity besprechen …** bleibt für
eine einzelne, ausdrücklich bestätigte Bild-Frage verfügbar, auch ohne
automatische Erfassung bei Sprachfragen.

## Debug-Terminal

**Debug-Terminal** im MiniTrinity-Menü zeigt die laufenden Mac-Protokolle:
Mikrofon-/Ausgabegerät, Live- und endgültige Transkription, Wakeword-Entscheidung,
Bildübertragung, LLM-Status, Eve-TTS-Prüfung und empfangenes Audio.
Erneutes Anklicken oder Schließen blendet nur dieses Fenster aus; Trinity läuft weiter.
Die Anzeige enthält Gesprächstext, daher nicht vor Studierenden oder in einer
Bildschirmfreigabe öffnen. Es handelt sich um ein lesendes Protokollfenster,
nicht um eine Shell mit Eingabemöglichkeit.

Im **Vortrag/Wakeword-Modus** werden nur Fragen mit erkanntem „Trinity“ beantwortet.
Bei falsch transkribiertem Wakeword steht der Grund ausdrücklich im Debug-Terminal.
Für einen direkten Schreib-/Gesprächstest **Gesprächsmodus → Büro · Konversation**
wählen; dort braucht nicht jede Frage das Wakeword.

## Erarbeiteten Text einsetzen

1. Trinity den gewünschten Text formulieren lassen. MiniTrinity merkt sich die
   letzte sichtbare Antwort des Servers.
2. Das Zielprogramm öffnen und im MiniTrinity-Menü **Letzte Antwort an
   Cursorposition einsetzen …** wählen.
3. Den vorgeschlagenen Text im Dialog prüfen und bei Bedarf ändern. Nach
   **Einsetzen** innerhalb von vier Sekunden die gewünschte Stelle im
   Zielprogramm anklicken.

Trinity prüft unmittelbar vor dem Einfügen erneut, ob **genau das bestätigte
Fenster** im Vordergrund steht. Sonst wird abgebrochen. Der Text wird als
reiner Text über die Zwischenablage eingefügt; die bisherige Zwischenablage
wird überschrieben. Falls die Ziel-App das Einfügen unterstützt, lässt sich
das Ergebnis dort mit **⌘Z** rückgängig machen.

Für das Einfügen benötigt macOS eventuell **Datenschutz & Sicherheit →
Bedienungshilfen**. Manche Anwendungen oder geschützte Felder erlauben kein
automatisches Einfügen. Bitte zunächst in TextEdit mit einem Wegwerftext testen.
Die Freigabe muss für den tatsächlich laufenden Trinity-Client gelten, nicht
nur für Codex/Terminal. Beim expliziten Diktatstart fordert Trinity fehlenden
Zugriff selbst an. Den angeforderten Eintrag in macOS erlauben und Trinity
danach beenden und neu starten. Das Debug-Terminal nennt getrennt `AX`
(Dokument lesen/auswählen) und `Tastatureingabe` (Einfügen).

## Sprachgesteuertes Schreiben in TextEdit (erste Ausbaustufe)

Mac-Mikrofon auswählen, ein **TextEdit-Dokument** aktivieren und die
Einfügestelle anklicken. Die Sprachbefehle brauchen keinen Klick auf
MiniTrinity:

Alternativ im MiniTrinity-Menü **Diktat starten · TextEdit** wählen;
derselbe Menüpunkt heißt währenddessen **Diktat stoppen · TextEdit**.
Ein **roter Rahmen** um das MiniTrinity-Icon (auch um das schwebende Gesicht)
kennzeichnet den aktiven Diktatmodus, nicht bloß das Ansehen eines Fensterbilds.
Der Rahmen verschwindet bei Stopp, einem Wechsel des Ziel-Fensters oder Mikrofons
und bei einem Verlust der Serververbindung. Der bisherige manuelle Menüpunkt
„Aktives Fenster mit Trinity besprechen“ entfällt; Bildschirmfragen erfassen das
Fenster weiterhin automatisch. Die normale Toolbar behält die manuelle Bild-Frage.

- „Diktat starten“ (ohne Wakeword) oder „Trinity, ich diktiere jetzt“ – beginnt das Diktat; alle folgenden
  abgeschlossenen Sprachstücke werden als Text eingefügt.
- „Diktat beenden“ oder „Diktat Ende“ (ohne Wakeword) – beendet es. Nur diese
  vollständigen Äußerungen gelten als Steuerbefehl, nicht längere Sätze, die sie erwähnen. Zusätzlich können
  die expliziten Befehle zur Fenstererfassung während des Diktats benutzt werden.
- „Einfügen“ – setzt die letzte Serverantwort an der aktuellen Stelle ein.
- „Trinity, fasse das Diktat zusammen“ – erstellt eine Zusammenfassung unter
  dem zuletzt erfassten Diktatblock.
- „Trinity, überarbeite das Diktat“ – erstellt darunter eine zweite Fassung.
  „Formuliere das besser“ funktioniert ebenfalls ohne Wakeword.
- „Trinity, übernimm die neue Fassung“ – ersetzt den erfassten Block nach
  Prüfung und entfernt die Vorschau.

Zusammenfassen, Überarbeiten und „Übernimm die neue Fassung“ funktionieren nach
„Diktat Ende“ auch ohne Wakeword. Erst die ausdrücklich angeforderte Übernahme
ersetzt das Original; ein Vorschlag allein tut das nicht. Englische Fachbegriffe,
Namen und Zahlen sollen erhalten bleiben. Diktate über 12.000 Zeichen werden
nicht stillschweigend abgeschnitten, sondern mit einer Bitte um kürzere Abschnitte abgelehnt.
Nach einem App-Neustart kann stattdessen vorhandener Text in TextEdit markiert
und mit denselben Befehlen bearbeitet werden. Nur dieser markierte Bereich wird
als Original gebunden; Text davor und danach wird nicht zum Umschreiben gesendet.
- „Trinity, lösche unsere Gedanken“ – fragt nach. Erst „Trinity, ja,
  Gedankenblock löschen“ entfernt den erfassten Block; eine Zusammenfassung
  muss bereits vorhanden sein.
- „Trinity, Bearbeitung abschließen“ – gibt die Bereichsbindung frei, ohne
  das Dokument zu verändern. Danach können andere Texte eingesetzt oder ein
  neues Diktat begonnen werden.
- „Trinity, was kannst du hier beim Schreiben tun?“ – spricht eine knappe
  Befehlshilfe. „Trinity, zeig mir die Schreibbefehle“ blendet die Liste kurz
  auf dem Mac ein. „Trinity, schreibe die Schreibbefehle hier hinein“ setzt
  sie auf ausdrücklichen Wunsch ins Dokument.

Löschen und Ersetzen sind auf den von Trinity erfassten Diktatblock und **das
gleiche, unveränderte TextEdit-Dokument** begrenzt. Externe Bearbeitungen oder
ein Fensterwechsel brechen die Aktion ab. Das Einfügen geschieht als Klartext
über die Zwischenablage; deren bisheriger Inhalt wird überschrieben. Die
Tastenkombination ⌘Z bleibt die Rückfallebene. Nicht in anderen Apps oder
vertraulichen Dokumenten testen, bis der TextEdit-Ablauf geprüft wurde.

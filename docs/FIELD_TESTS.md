# Feldtests für Trinity 0.19

Je Versuch notieren: Gerät, Mic-/Lautsprecherbesitzer, Modus, Uhrzeit,
Ende der Frage bis erster hörbarer Antwort, Satzpausen, Fehlverhalten.
Bei einem Fehler stoppen, Uhrzeit/Frage melden; keine spontanen Modellwechsel.
Keine vertraulichen Daten für Tests verwenden.

1. **Begriff ohne Agent:** Büro wählen. „Trinity, erkläre den Unterschied
   zwischen Korrelation und Kausalität in drei kurzen Sätzen.“ Erwartung:
   richtige Erklärung, kein Sandbox-Player, keine alte oder englische Antwort.
2. **Fachbegriffe/Umlaute:** „Trinity, erkläre für größere Übungen den Unterschied
   zwischen Overfitting und Underfitting.“ Erwartung: Anglizismen erlaubt,
   saubere Aussprache von für/größer/Übungen, kein fÃ¼r.
3. **Flüssiges Streaming:** „Trinity, erkläre in acht kurzen Sätzen, warum Wasser
   beim Gefrieren sein Volumen verändert.“ Ganze Antwort hören: kein fehlender
   Satz, keine auffälligen langen Satzpausen, kein neuer STT-Beitrag von Trinity.
4. **Abbruch:** Während der Antwort stoppen/doppeltippen; danach „Trinity, was
   bedeutet Latenz? Ein Satz.“ Erwartung: keine Fortsetzung der alten Antwort
   und kein alter Beitrag im Chat als vollständige neue Antwort.
5. **Getrennte Geräte:** G2 als Mic, iPad als Ausgabe; dann Mac als Mic und
   iPhone als Ausgabe. Pro Auswahl nur ein Eingang/ein Ausgang, G2 nie TTS.
   Wechsel während TTS: Rest kann nach Verbindungsaufbau weiterlaufen, eine
   kurze Übergangslücke ist möglich; weder Neustart noch Doppelwiedergabe.
6. **Vision:** iPad-Folie mit Tabelle und Mac-Fenster gleichzeitig offen.
   „Trinity, erkläre die Tabelle, die du jetzt siehst.“ Dann Ausgabe wechseln
   und erneut fragen. Nur das Ausgabegerät darf Bildkontext liefern.
7. **Explizite Berechnung:** „Trinity, erstelle Python-Code, der die Korrelation
   für X = 1, 2, 3 und Y = 2, 4, 6 berechnet.“ Erwartung: Sandbox vorbereitet,
   keine falsche Behauptung, der Server hätte Code bereits ausgeführt.
8. **Diktat:** In einer leeren TextEdit-Testdatei Cursor setzen. „Trinity,
   Diktat starten“, zwei Absätze sprechen, „Diktat stoppen“, „Fasse das Diktat
   darunter zusammen“. Vorher/Nachher und Auswahl prüfen. Fremde Apps erst
   in unkritischen Testdokumenten prüfen; keine Mail automatisch senden.
9. **Memory:** „Trinity, merke dir: Unser Testprojekt heißt Lernlabor Aurora.“
   Später/neues Gerät: „Wie hieß unser Testprojekt heute?“ Erwartung: aus
   gespeichertem Gespräch abrufbar. Eine richtige Antwort beweist keine
   vollständige Archivierung aller Wakeword-freien Hörphasen.
10. **20 Minuten Diskurs:** Vortrag-Modus, schnell sprechen, Themenwechsel,
    Rückfrage alle zwei Minuten. Bei Minute 2/10/20 dieselbe kurze Begriffsfrage
    stellen und Latenz vergleichen. Kein Rückfall auf längst erledigte Fragen.
11. **Medien:** Je ein kurzes Bild-/Liedauftrag; Player öffnen, löschen und Talk
    erneut öffnen. Maximal ein Ergebnis pro Auftrag; gelöscht bleibt verborgen.
    „Erstelle ein lokales …“ muss ComfyUI nutzen. Diese Tests können Kosten
    verursachen; nicht automatisiert mehrfach wiederholen.
12. **Netzunterbrechung:** Während einer Antwort Tailscale/WLAN kurz trennen,
    wieder verbinden und eine neue Frage stellen. Keine verspätete Altantwort.

Nur iPad: Die RØDE-/HDMI-Tests und der 60-Minuten-Test stehen im Companion unter
`docs/HOERSAAL_AUDIO.md`. HDMI-Verlust muss Live-Mic sofort stummschalten;
kein Fallback der verstärkten Stimme auf den iPad-Lautsprecher.

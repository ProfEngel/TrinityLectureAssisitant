# Sprechstelle in der schwebenden Trinity-App

Stand: 17. September 2026.

Der Avatar zeigt ausschließlich die Augen, ohne Zusatzknöpfe oder Text.
Doppelklick verschiebt ihn in die macOS-Menüleiste. Die kleinen Augen blinzeln
alle fünf bis neun Sekunden kurz. Im Menü gibt es „Avatar anzeigen“, Chat,
Ergebnisse/Hinweise, Audioauswahl und Einstellungen. Ein Rechtsklick auf den
großen Avatar bietet dieselbe Audioauswahl und den Wechsel in die Menüleiste.
Der Menüleistenmodus bleibt über Neustarts erhalten. Ergebnisse öffnen dort
kein zusätzliches Fenster automatisch, sondern markieren den Menüeintrag als „Neu“.

Standard ist „Audio durch Farbe anzeigen (Orange/Weiß)“: orange bei lokal aktivem
Mikrofon oder Sprachausgabe, sonst weiß. Die Augen bleiben grün. „Audiopunkt
anzeigen“ ist unabhängig zuschaltbar und standardmäßig aus. Beide Einstellungen
bleiben erhalten. Ohne Farbanzeige kann „Weiße MiniTrinity“ wieder zwischen
Weiß und Schwarz umschalten. „Sprachausgabe stumm“ schaltet nicht das Mikrofon ab;
Trinity kann deshalb weiterhin orange sein.

Das Gesicht ist jetzt 45 × 36 Zeicheneinheiten groß. Ohne Audiopunkt entfällt
auch dessen reservierter Platz; die MiniTrinity erscheint dadurch kräftiger.
macOS bestimmt die endgültige Anzeigegröße.

„Hier auf dem Mac antworten“ und „Sprachausgabe stumm“ nutzen
denselben authentifizierten `/speaker`-Endpunkt wie die Apple-Companion-App.
Die Auswahl wird in der gemeinsamen Konfiguration gespeichert; Desktop-TTS und
Eve berücksichtigen sie bereits. Ein Companion kann anschließend wieder selbst
die Ausgabe übernehmen. Stummschalten betrifft die gemeinsame Sprachausgabe.

Die Schaltfläche startet keine neue Konversation und spielt keine alte Antwort
erneut ab. Sie bestimmt das Ziel der folgenden Antworten. Mikrofon und Modell
müssen weiterhin betriebsbereit sein.

Die tatsächlich per LaunchAgent gestartete Mac-Instanz liegt unter
`/Users/matmax/Projects/trinity-voice-runtime-desktop`. Sie ist ein Git-Worktree
des TrinityLectureAssisitant-Repositories. `/Users/matmax/Trinity_Assistant`
ist ein anderer, älterer lokaler Stand; die Änderung wurde gezielt in der
tatsächlich laufenden Instanz umgesetzt.

Prüfung: `tests/test_desktop_speaker_control.py` testet den authentifizierten
Wechsel vom iPad zum Desktop, Stummschalten und erneute Übernahme durch das iPhone
gegen einen lokalen Testserver. Dazu wurden die Bridge- und lokalen Eve-Tests
ausgeführt. `tests/test_avatar_tray.py` prüft außerdem Doppelklick ohne
versehentliches Chatfenster, Wechsel und Rückkehr, gespeicherten Startmodus,
fehlende Menüleistenunterstützung, Blinkbilder, Farbumschaltung und den getrennten
Audioindikator. `tests/test_desktop_audio_activity.py` prüft aktive/veraltete
Prozessmarker.

Bei einem Neustart zuerst die alte Laufzeit vollständig beenden lassen und erst
danach starten: Ein unmittelbares `launchctl kickstart -k` kann die neue
Voice-Laufzeit starten, während die alte ihren Port noch freigibt.

# YuE2-Musik in Trinity

Musikaufträge werden zentral auf dem Trinity-Server vorbereitet und über den
konfigurierten ComfyUI-Server ausgeführt. Die Clients brauchen keine eigenen
Musikmodelle. `comfyui.music_workflow` wählt `audio_yue2_text2music_API.json`;
ohne diese Einstellung bleibt für bestehende Standalone-Installationen AceStep
erhalten. Bilder und Musik verwenden getrennte Workflows.

Beispiele:

- „Trinity, mach uns ein Fahrstuhlmusik-Lied.“
- „Trinity, erstelle einen Rocksong der 80er.“
- „Trinity, erstelle ein typisches Drake-Lied.“

Das vorhandene LLM erstellt einen englischen Stil-Brief, kurze originale Lyrics
in der Sprache der Anfrage und eine Demo-Länge von 15–55 Sekunden, standardmäßig
40 Sekunden. Fahrstuhlmusik, Instrumental und „ohne Gesang“ bekommen keine Lyrics.
Künstlerreferenzen werden in allgemeine musikalische Merkmale übersetzt, nicht
in eine Kopie der Stimme oder bestehender Songtexte. Der YuE2-Workflow erhält
einen begrenzten `max_duration` sowie dieselbe feste Audio-Latentlänge.

Nach der Generierung lädt Trinity die MP3 mit dem tatsächlichen ComfyUI-
Ausgabeunterordner herunter und liefert einen Audio-Payload mit Player und Lyrics.
Mac, iPad und iPhone verwenden ihre vorhandenen Medien-Player. Die G2 kann den
Auftrag anstoßen, aber hat keinen Lautsprecher. Mobile Wiedergabe per Play-Taste;
kein garantiertes automatisches Starten im Hintergrund oder gleichzeitiges
Abspielen auf allen Geräten. Browser-Autoplay hängt vom Client ab.

Keine Cloud-Ersatzgenerierung bei fehlender ComfyUI-Verbindung.
Die Renderzeit ist nicht gleich der Lieddauer und kann mehrere Minuten betragen.
Bild-/Musikagenten arbeiten derzeit synchron; vollständige asynchrone Entkopplung
vom Sprachdialog bleibt ein nächster Schritt.

Prüfung am 2. Oktober 2026: echtes LLM-Briefing, YuE2-Render, MP3-Download und
ffprobe-Dauerprüfung erfolgreich: angefordert 20 Sekunden, Ergebnis 20,04 Sekunden.
25 Tests für Routing, Bildagenten, kurze Musik-Briefs, Workflow-Injektion,
Download-Unterordner und Sprach-Backend bestanden. Reale Wiedergabe auf jedem
physischen Gerät muss noch durch den Nutzer geprüft werden.

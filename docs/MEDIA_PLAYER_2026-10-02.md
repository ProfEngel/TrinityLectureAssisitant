# Medien-Player und Rasterbild-Routing (02.10.2026)

Companion 0.18.7 / Build 197 stellt links in der einzeiligen Kopfleiste wieder
einen Medienknopf bereit. Orange bedeutet laufender Auftrag; Grün bedeutet,
dass ein gespeichertes Medienergebnis vorhanden ist. Tippen öffnet das letzte
Medienergebnis im vorhandenen Popup-Player, unabhängig von der aktuellen
Ansicht. Reine Textantworten zählen nicht als Medienergebnis. Schließen des
Popups entfernt das Ergebnis nicht aus der Historie.

Der Server meldet Beginn/Ende von Bild- und Musikaufträgen über bestehende
`trinity.debug`-Ereignisse mit Stage `Media`. Auch Sprachaufträge erhalten so
die Betriebsanzeige; bei Ausführungsfehlern wird Ende ebenfalls gemeldet.

Bild-, Schaubild- und Diagramm-Erstellungswünsche werden vor anderen Skills
auf den Rasterbild-Agenten beschränkt. Standard ist ComfyUI; ein ausdrücklich
externer Wunsch erlaubt den externen Bild-Agenten. Aktuelle Folien- oder
Fensterbilder dürfen diesen Erstellungsweg nicht blockieren. Musikbegriffe
innerhalb eines Bildwunsches lösen keine Musikgenerierung aus.

Nach Fehlern oder fehlendem Bild-Agenten endet die Anfrage mit einer ehrlichen
Fehlermeldung. Kein LLM-Code-/Mermaid-Ersatz und kein impliziter Cloud-Fallback.
Bildanalyse bleibt eine normale Vision-Anfrage.

Verifikation: 42 Python-Tests erfolgreich; iOS-Geräte- und Simulator-Builds
erfolgreich; signierte Version 0.18.7 auf iPad/iPhone installiert. Die physische
Sprachbedienung und Player-Wiedergabe sind anschließend vom Nutzer zu testen.

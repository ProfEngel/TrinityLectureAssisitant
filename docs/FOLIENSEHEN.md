# Foliensehen im Companion

Stand: 17. September 2026.

Unter Einstellungen → Foliensehen lässt sich „Aktuelle Folie mit Trinity teilen“
abschalten. In der Vortragsansicht werden beim Seitenwechsel der Folientext und
ein Bild der aktuellen PDF- bzw. HTML-Folie über die authentifizierte Bridge
übertragen. Der Diagnosezustand erscheint ausschließlich in den Einstellungen,
nicht in der Vortragsansicht. Er unterscheidet bestätigte Bilder, reinen Text,
Verbindungsfehler und ältere Bridges ohne Folien-Endpunkt. PDF-Handschrift ist derzeit
nicht Bestandteil des Folienbilds.

Die nächste Modellanfrage aus Chat oder Sprache bekommt diese aktuelle Folie als
Referenzmaterial. Es erfolgt keine eigenständige Modellantwort oder Voranalyse
bei jedem Seitenwechsel. „Wie erkläre ich diese Tabelle?“ kann damit auf das
aktuelle Bild Bezug nehmen. Das aktive Modell muss Bilder unterstützen; bei
einem abgewiesenen Bildrequest wird auf den extrahierten Text zurückgefallen.
Ein synthetischer Tabellenbildtest mit dem aktuell konfigurierten Modell
Gemma4_26B_WS_BUERO wurde am 17.09.2026 korrekt beantwortet.

Korrekturen vom Nachmittag: Bilder werden vor dem Upload auf maximal 1600 Pixel
Kantenlänge und 2 MB gebracht, statt große Retina-Bilder still zu verwerfen.
Nach Profilwechsel wird die weiterhin sichtbare Folie erneut erfasst. Alte
Editor-Instanzen dürfen den Kontext eines neueren Editors nicht löschen.
HTML erkennt zusätzlich Reveal- und sichtbarkeitsbasierte Folien und erneuert
Snapshots für dynamische Diagramme. Fehlender Bildkontext wird dem Modell
ausdrücklich mitgeteilt; Modellfehler werden nicht mehr als „Faden verloren“
verschleiert. Eine ältere Windows-Installation benötigt dieselben Desktop-Änderungen;
ein Companion-Update allein aktualisiert den Windows-Server nicht.

Es wird nur die aktuelle Folie lokal gespeichert, keine Bildhistorie. Der Kontext
ist an Profil und Konversation gebunden, wird beim Verlassen gelöscht und ohne
Erneuerung nach 90 Sekunden ignoriert. Sequenznummern verhindern, dass verspätete
Uploads eine neuere Folie überschreiben. Folientext ist ausdrücklich untrusted
Referenzmaterial, keine Handlungsanweisung.

Die Bilddaten gehen mit der folgenden Frage an den konfigurierten Modellserver.
Ein Notierauftrag verwendet die vorhandenen Notiz-/Werkzeugfunktionen; durch
Foliensehen allein wird keine Präsentationsdatei verändert.

Automatisiert geprüft: Kontextumfang, Reihenfolge, Ablauf, Bildvalidierung,
Übergabe an Modellnachrichten sowie bestehende Brain-/Bridge-/Voice-Tests.
`tests/test_lecture_voice_integration.py` prüft den vollständigen Backendweg vom
HTTP-Upload bis zur multimodalen Sprach-Modellanfrage und das anschließende Löschen.
Dieser Backendweg wurde auch mit einem echten JPEG, isolierter Test-Bridge,
TrinityConversationBackend, TrinityBrain und dem konfigurierten Gemma-Modell
ausgeführt: Ein ausschließlich im Bild enthaltener Tabellenwert wurde korrekt
als „73“ gelesen. Dafür wurden weder echte Sessiondaten noch Notizen verändert.
Ein vollständiger Sprachdialog mit einer echten Präsentation auf dem iPad ist
noch vom Nutzer praktisch zu prüfen.

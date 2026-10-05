# Gemeinsame Mediengenerierung (02.10.2026)

`media_generation.provider = kie` wählt kie.ai für Bilder und Musik auf dem
gemeinsamen Server und im Mac-Standalone-Betrieb. Mobile Clients benötigen
keinen Provider-Schlüssel: Sie verwenden den vorhandenen Medien-Player und
den geschützten Trinity-Server.

- Bildmodell: `gpt-image-2-5-flare-text-to-image`, `resolution=2K`,
  `aspect_ratio=16:9`, deutsche Bildbeschriftungen, dezente Pastellfarben.
- Musikmodell: `ai-music-api/generate`, `input.model=V6`, benutzerbestätigt
  statt des laut aktueller Dokumentation eingestellten V5.5. Kurze Original-
  Demos mit 15–55 Sekunden; instrumentale Wünsche ohne Songtext/Gesang.
- „lokal“ oder „ComfyUI“ im Erstellungswunsch überspringt kie.ai vollständig.
- `comfyui_fallback=true`: ComfyUI übernimmt nur nach sicherem Fehler vor
  einem Ergebnis bzw. einem endgültig fehlgeschlagenen kie.ai-Auftrag.
  Unklare POST-Übertragung, unklarer Auftragsstatus, laufender Auftrag oder
  fehlgeschlagener Download eines fertigen Ergebnisses lösen keinen zweiten
  Generierungsauftrag aus.

Der Schlüssel liegt im bestehenden Workbench-Secretstore (Dateimodus 0600),
nicht in Agentdateien, Prompts oder Companion-Apps. API-Requests verwenden
Bearer-Authentifizierung, `/jobs/createTask` und `/jobs/recordInfo`.

`background_jobs=true` bestätigt Aufträge sofort und veröffentlicht das fertige
Medium als `media-job`-Chatereignis mit `payload_html`. Damit muss die Voice-
HTTP-Schnittstelle nicht während der Generierung warten. Persistente
Idempotenz in `memory/media_jobs.sqlite3` unterbindet erneute Generierung der
gleichen normalisierten Anfrage innerhalb einer Stunde, auch nach Neustart.
Ein bewusst neuer Auftrag muss anders formuliert werden, z.B. „Erstelle ein
neues …“. Fehlgeschlagene Aufträge werden nicht automatisch erneut geschickt.

Ursache der beobachteten drei ComfyUI-Lieder: wiederholte Voice-HTTP-Anfragen
nach Zeitüberschreitungen; zudem war die Musik-Erkennung zu weit gefasst.
„Damit du Bilder und Musik machen kannst. Was hältst du davon?“ ist nun kein
Erstellungsauftrag mehr. Die YuE2-Vorlage hat bereits `batch_size=1`.

Trinity veröffentlicht pro Auftrag ein Medium. Suno kann intern mehrere
Varianten liefern; Trinity lädt und zeigt nur eine Audiodatei.
Kein Mermaid-Ersatz und kein fal.ai-Fallback im kie.ai-Modus.

Offizielle API-Referenzen:
- https://docs.kie.ai/43283988e0
- https://docs.kie.ai/suno-api/generate-music
- https://docs.kie.ai/market/common/get-task-detail

Verifikation: 52 Python-Tests erfolgreich; echtes kie.ai-Bild mit deutschen
Beschriftungen erzeugt; echtes Suno-V6-Audio heruntergeladen. Companion 0.18.9
beendet die orange Statusanzeige auch bei abgefangenen Doppelaufträgen/Fehlern.

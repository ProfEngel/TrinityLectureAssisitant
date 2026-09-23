# Trinity ohne Windows-VM: kontrollierter Linux-Server

Trinity kann den textuellen Kern, Memory, Bridge und die CUDA-Sprachpipeline
auf demselben Linux-Host betreiben. Das Profil `trinity-linux-server` verbindet
Parakeet-STT und Qwen3-TTS mit dem **lokalen** Trinity-Kern. Das bisherige
`eve-linux-gpu-server` bleibt unverändert und leitet weiterhin an einen
externen Kern weiter. Standalone-Profile auf Mac und Windows bleiben erhalten.

## Vor dem Umschalten

1. Die laufende Linux-Installation, lokale Änderungen, Dienste und Ports
   inventarisieren. Nie über eine aktive Installation hinweg blind pullen.
2. Betriebsdaten, Konfiguration, Soul/User, RAG, Memory und Schlüssel getrennt
   vom Git-Checkout sichern. Keine Secrets in Git oder Service-Logs schreiben.
3. Linux-Trinity in einem separaten Checkout mit eigener Runtime und freien
   Testports installieren. Die bestehende Voice-Pipeline und die Windows-VM
   bleiben dabei aktiv.
4. Im privaten `core/config.json` LLM-Endpunkt, Persona, Memory und benötigte
   Agenten gezielt konfigurieren. Die Windows-Konfiguration nicht vollständig
   kopieren: Windows-Pfade und gerätespezifische Integrationen sind unbrauchbar.
5. Bridge und Voice nur an Tailnet/private Interfaces binden und mit eigenen
   Zugangstokens schützen. Für iPhone/iPad müssen Bridge- und Voice-Adresse
   auf denselben Linux-Host zeigen. Niemals öffentliche Ports öffnen.

## Start als ein betreuter Prozess

Nach erfolgreichem Test und mit freien Ports:

```text
python trinity_cli.py server --host 100.70.50.6 --port 8765 \
  --voice-profile trinity-linux-server
```

Der Server betreut Trinity-Kern, Bridge und Sprachpipeline. Ohne
`--voice-profile` bleibt das bisherige server-only-Verhalten unverändert.
Der Sprachpfad ist erst nach einem echten STT→Memory/LLM→TTS-Test freigegeben;
ein HTTP-Healthcheck allein genügt nicht.

## Noch nicht Teil dieses Schritts

- Der Desktop-Umschalter zu einem reinen Remote-Client ist noch zu bauen;
  die bisherige Desktop-Checkbox allein routet noch nicht alle Funktionen.
- Bildschirminhalt, Folien und Dateien brauchen einen authentifizierten
  Upload-/Kontextkanal mit Freigabe am jeweiligen Client. Dateien dürfen nicht
  nur als lokaler Pfad an den Linux-Host gesendet werden.
- Der TrinityHUB ist ein eigener Dienst. Aufrufe seiner Werkstätten benötigen
  definierte APIs und Berechtigungen; ein eingebetteter Browser ist noch keine
  sichere Agentenverbindung.
- Alte Windows-Dienste erst nach Vergleich von Antworten, Memory, Agenten,
  Vortrags-Vision, Mobilgeräten und Rückfallweg abschalten.

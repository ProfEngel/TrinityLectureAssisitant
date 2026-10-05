# 🖼️ ComfyUI Agent

## Qwen-Image 2.1

Unterstützt `qwenimage2.1_t2i_API.json` und für ein Referenzbild
`qwenimage2.1_1i2i_API.json`. Der Agent injiziert den Auftrag in
`TextEncodeQwenImage21.inputs.prompt`, statt die Flux-Knoten zu verwenden.
Das Modell und der Textencoder werden unverändert aus dem gewählten Workflow
geladen. Der Bild-Brief wird über Trinitys vorhandenes LLM erstellt:
englische präzise Beschreibung, kurze exakt zitierte Beschriftungen,
gedeckte Pastellfarben, klare Layout-Hierarchie und keine erfundenen Zahlen.
Diese Policy gilt nur für den Bildauftrag, nicht für Trinitys Gesprächs-Soul.

ComfyUI ist zentral im Trinity-Server konfiguriert. Companion und Mac-Tunnel
brauchen keine eigenen Bildmodelle. Ergebnisse sind Medien-Payloads;
automatisches Einsetzen in fremde Rich-Text-Dokumente ist nicht enthalten.
Infografik-Beschriftungen müssen wie bei jeder generativen Bildausgabe geprüft
werden. Weitere Mehrbild-Workflows werden noch nicht automatisch ausgewählt.

Grundlagen: https://huggingface.co/Qwen/Qwen-Image-2.1 und
https://huggingface.co/Comfy-Org/Qwen-Image-2.1

**Skill-Typ:** Bildgenerierung (lokal via Tailscale)  
**Trigger-Keywords:** `lokales bild`, `lokal generier`, `lokal erstell`, `auf meinem server`, `auf dem server`, `flux render`, `comfyui`, `flux bild`, `flux erstell`, `flux generier`, `render ein`, `rendere`, `flux2`

---

## Funktionsweise

1. **Ping:** Prüft ob der ComfyUI-Server erreichbar ist (`/system_stats`)
2. **Prompt-Extraktion:** Nutzt das LLM um einen SD-Prompt aus der Anfrage zu extrahieren
3. **Workflow-Injection:** Lädt `workflows/Flux2_Klein_T2I_API.json` und injiziert den Prompt in Node 14
4. **Queue:** Sendet den Workflow via `POST /api/prompt` an ComfyUI
5. **Polling:** Wartet bis das Bild fertig ist (`/api/history/{prompt_id}`)
6. **Download:** Lädt das Bild herunter → `media/output/`
7. **UI:** Zeigt das Bild im Trinity-Nebenfenster an
8. **Telegram (optional):** Sendet das Bild als Foto an den konfigurierten Chat

---

## Verzeichnisstruktur

```
agents/comfyui_agent/
├── workflows/
│   └── Flux2_Klein_T2I_API.json   # Flux2 Klein 9B – Text to Image
├── media/
│   ├── input/    ← Eingabe-Bilder für zukünftige Img2Img-Workflows
│   └── output/   ← Generierte Bilder (gitignored)
├── script.py
└── skill.md
```

---

## Einstellungen (Settings UI: 🔑 APIs & Bild → ComfyUI Server)

| Feld | Beschreibung |
|------|-------------|
| ComfyUI aktivieren | Master-Toggle |
| Server URL | Tailscale-IP + Port, z.B. `http://100.x.y.z:8188` |
| Standard-Workflow | Dateiname aus `workflows/` |
| 🔗 Verbindung testen | Pingt `/system_stats`, zeigt Python-Version bei Erfolg |

> **Sicherheit:** Server-URL liegt in `core/config.json` (gitignored).  
> `media/input/` und `media/output/` sind ebenfalls gitignored.

---

## Zukünftige Erweiterungen

- `Flux_Img2Img.json` – Bild-zu-Bild Workflow (Input aus `media/input/`)
- Workflow-Dropdown im Settings-UI wenn mehrere Workflows vorhanden

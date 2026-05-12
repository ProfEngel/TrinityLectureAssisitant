# 🖼️ ComfyUI Agent

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
| Server URL | Tailscale-IP + Port, z.B. `http://100.122.13.123:8188` |
| Standard-Workflow | Dateiname aus `workflows/` |
| 🔗 Verbindung testen | Pingt `/system_stats`, zeigt Python-Version bei Erfolg |

> **Sicherheit:** Server-URL liegt in `core/config.json` (gitignored).  
> `media/input/` und `media/output/` sind ebenfalls gitignored.

---

## Zukünftige Erweiterungen

- `Flux_Img2Img.json` – Bild-zu-Bild Workflow (Input aus `media/input/`)
- Workflow-Dropdown im Settings-UI wenn mehrere Workflows vorhanden

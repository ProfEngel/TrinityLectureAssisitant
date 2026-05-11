# Graph Report - Trinity_Assistant  (2026-05-11)

## Corpus Check
- 27 files · ~786,576 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 168 nodes · 207 edges · 15 communities detected
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 6 edges (avg confidence: 0.65)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `eb148026`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 15|Community 15]]

## God Nodes (most connected - your core abstractions)
1. `SettingsWindow` - 15 edges
2. `TrinityBrain` - 14 edges
3. `NativeMorpheusEar` - 12 edges
4. `MorpheusEar` - 11 edges
5. `ContentWindow` - 8 edges
6. `ContentResizeFilter` - 7 edges
7. `set_state()` - 7 edges
8. `ChatWindow` - 6 edges
9. `TrinityWindow` - 6 edges
10. `WebEngineDragFilter` - 5 edges

## Surprising Connections (you probably didn't know these)
- `ContentWindow` --inherits--> `QMainWindow`  [EXTRACTED]
  trinity_app.py → core/settings_ui.py
- `ChatWindow` --inherits--> `QMainWindow`  [EXTRACTED]
  trinity_app.py → core/settings_ui.py
- `TrinityWindow` --inherits--> `QMainWindow`  [EXTRACTED]
  trinity_app.py → core/settings_ui.py
- `NativeMorpheusEar` --uses--> `TrinityBrain`  [INFERRED]
  core/transcriber_native.py → core/brain.py
- `NativeMorpheusEar` --uses--> `MorpheusEar`  [INFERRED]
  core/transcriber_native.py → core/transcriber.py

## Communities (27 total, 5 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.12
Nodes (9): QMainWindow, QObject, ChatWindow, ContentResizeFilter, ContentWindow, Passt Fenstergröße an Bildgröße an wenn IMAGE_PAYLOAD gesetzt., EventFilter der auf dem WebEngine-FocusProxy lauscht und Resize an den Rändern e, TrinityWindow (+1 more)

### Community 1 - "Community 1"
Cohesion: 0.23
Nodes (6): has_trigger(), MorpheusEar, Prüft ob das Wake-Word (oder eine Variante) im Text vorkommt., Lädt STT-spezifische Settings aus der config.json., Wird vom sounddevice Stream aufgerufen., set_state()

### Community 2 - "Community 2"
Cohesion: 0.19
Nodes (4): Lädt die Konfiguration aus der config.json., Lädt alle Live-Skills aus dem agents/ Ordner dynamisch beim Start., Hilfsmethode für interne LLM-Aufrufe (z.B. Context Enrichment)., TrinityBrain

### Community 4 - "Community 4"
Cohesion: 0.27
Nodes (4): NativeMorpheusEar, Native macOS STT loop for Trinity.  This module uses Apple's Speech framework fo, MorpheusEar variant backed by macOS SFSpeechRecognizer., MorpheusEar

### Community 5 - "Community 5"
Cohesion: 0.38
Nodes (5): _build_image_payload(), execute(), _generate_image_fal(), Erzeugt ein Bild mit fal.ai und speichert es lokal., Erzeugt das HTML für die Anzeige des generierten Bildes – Fenster passt sich an

### Community 6 - "Community 6"
Cohesion: 0.38
Nodes (6): can_handle(), _convert_number_words(), execute(), Führt die Timer-Logik aus und liefert Payload sowie Suchkontext zurück., Prüft, ob die Anfrage einen Timer-Befehl enthält., Hilfsfunktion zur Konvertierung von Zahlwörtern in Ziffern.

### Community 7 - "Community 7"
Cohesion: 0.38
Nodes (6): build_index(), chunk_pages(), extract_text_from_pdf(), Extrahiert sauberen Text aus einer PDF., Zerlegt Seitentext in überlappende Chunks., Hauptfunktion: PDFs lesen → Chunks → Embeddings → Speichern.

### Community 9 - "Community 9"
Cohesion: 0.53
Nodes (4): execute(), init(), _load_rag_index(), _load_rag_model()

### Community 10 - "Community 10"
Cohesion: 0.4
Nodes (4): can_handle(), execute(), Führt die Maps-Logik aus und liefert Payload sowie Suchkontext zurück., Prüft, ob die Anfrage einen Maps-Befehl enthält.

### Community 11 - "Community 11"
Cohesion: 0.5
Nodes (3): Skill: Session Summarizer Dieses Skript dient als Platzhalter/Logik-Rahmen für d, Simuliert die Verarbeitung einer Log-Datei.     In der Praxis würde hier die Dat, summarize_session()

## Knowledge Gaps
- **26 isolated node(s):** `EventFilter der auf dem WebEngine-FocusProxy lauscht und Resize an den Rändern e`, `Passt Fenstergröße an Bildgröße an wenn IMAGE_PAYLOAD gesetzt.`, `TrinityNative Launcher STT: macOS SFSpeechRecognizer (Apple Neural Engine, Deuts`, `Nutzt das native macOS 'say' Kommando.     Dies ist die schnellste und einfachst`, `MorpheusEar` (+21 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SettingsWindow` connect `Community 3` to `Community 0`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **Why does `TrinityBrain` connect `Community 2` to `Community 1`, `Community 4`?**
  _High betweenness centrality (0.031) - this node is a cross-community bridge._
- **Why does `QMainWindow` connect `Community 0` to `Community 3`?**
  _High betweenness centrality (0.029) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `TrinityBrain` (e.g. with `.__init__()` and `.__init__()`) actually correct?**
  _`TrinityBrain` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `NativeMorpheusEar` (e.g. with `TrinityBrain` and `MorpheusEar`) actually correct?**
  _`NativeMorpheusEar` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `MorpheusEar` (e.g. with `NativeMorpheusEar` and `TrinityBrain`) actually correct?**
  _`MorpheusEar` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `EventFilter der auf dem WebEngine-FocusProxy lauscht und Resize an den Rändern e`, `Passt Fenstergröße an Bildgröße an wenn IMAGE_PAYLOAD gesetzt.`, `TrinityNative Launcher STT: macOS SFSpeechRecognizer (Apple Neural Engine, Deuts` to the rest of the system?**
  _26 weakly-connected nodes found - possible documentation gaps or missing edges._
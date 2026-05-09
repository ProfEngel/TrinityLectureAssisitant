# Trinity Assistant v0.4.1

## 🔄 Architektur & Refactoring (Punkt 0 abgeschlossen)
- **Vollständige Modularisierung:** Die `core/brain.py` wurde endgültig von der RAG-Logik befreit.
- **Neuer RAG-Agent:** Die Skript/Buch-Suche (Retrieval-Augmented Generation) läuft nun als eigenständiger Skill unter `agents/rag_agent/`.
- **Skill-Standardisierung:** Alle Agenten-Ordner im `agents/`-Verzeichnis besitzen nun standardmäßig eine `skill.md` für konsistente Dokumentation.
- **Dynamisches Laden:** Die Kern-Architektur lädt Skills nun 100% dynamisch (inkl. optionaler `init()` Methode pro Skill).

## 🗺️ Roadmap Update
- Die Roadmap wurde um Phase 3 (Proaktiver Agentic Companion) und Phase 4 (Cognitive Evolution & Dreaming) erweitert.
- Vorbereitungen für das kommende 2-Minuten Heartbeat-System und UI-Bubbles sind abgeschlossen.

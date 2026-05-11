# 🗺️ Trinity Implementierungsplan - Phase 2

## 1. Hermes als Subagent (Spezialist)
- **Ziel**: Hermes als spezialisiertes Werkzeug für Trinity etablieren.
- **Rolle**: Trinity bleibt der IMMER verfügbare Direktkontakt und das primäre Interface. Sie filtert 90% der Anfragen.
- **Workflow**: Nur bei komplexen, tiefgehenden Aufgaben (Deep Research, Code-Analyse, Strategie) delegiert Trinity die Aufgabe an Hermes "auf Steroiden". Hermes liefert die Ergebnisse an Trinity zurück, und sie präsentiert sie.

## 2. RAG-Integration (Wissensbasis) - ✅ IMPLEMENTIERT
- **Ziel**: Trinity Zugriff auf deine Lehrinhalte geben.
- **Umgesetzt**: 
    - Integration der lokalen `sentence-transformers` Vektorsuche.
    - PDFs in `/RAG` werden automatisch indiziert.
    - RAG-Agent greift über Trigger-Wörter autonom auf das Wissen zu.

## 3. Dynamische Research-Widgets (Deep Research) - ✅ TEIL-IMPLEMENTIERT
- **Ziel**: On-the-fly Erstellung von Dashboards.
- **Umgesetzt**:
    - **Deep Research**: Der `websearch_agent` führt Tavily-Suchen durch und baut Echtzeit-Dashboards.
    - **Diagramme / Daten**: Der `stock_agent` visualisiert Kursdaten in Echtzeit (inkl. SVG-Sparklines).
    - **Schaubilder**: Der `image_agent` generiert edukative Grafiken auf Zuruf.
- **Offen**:
    - **YouTube**: Automatisches Einbetten relevanter Lehrvideos.

## 5. Plattform-Expansion (Native Apps)
- **Ziel**: Trinity über den Python-Launcher hinaus verfügbar machen.
- **Konzept**: 
    - **macOS App**: Verpackung als native Swift/AppKit Anwendung für bessere Systemintegration und Performance.
    - **iPad App**: Entwicklung einer Begleit-App, die das Dashboard und Trinitys Augen auf das iPad spiegelt (perfekt für das Pult während der Dozent im Raum herumläuft).
    - **Sync**: Nahtlose Synchronisation des Wissensstands zwischen Mac und iPad.

## 4. Persona & Rhythmus (Soul-Update) - ✅ IMPLEMENTIERT
- **Ziel**: Maximale Effizienz in der Kommunikation.
- **Umgesetzt**: 
    - Trinity hält sich ab sofort an die **2-3 Sätze** Regel (Brevity).
    - Feedback-Muster ("Einen Moment...") ist aktiv.
    - Trinity ist die Chefin, Hermes ist ihr Werkzeug.

---
*Status: Bereit für Umsetzung am Montag.*

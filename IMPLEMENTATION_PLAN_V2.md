# 🗺️ Trinity Implementierungsplan - Phase 2

## 1. Hermes als Subagent (Spezialist)
- **Ziel**: Hermes als spezialisiertes Werkzeug für Trinity etablieren.
- **Rolle**: Trinity bleibt der IMMER verfügbare Direktkontakt und das primäre Interface. Sie filtert 90% der Anfragen.
- **Workflow**: Nur bei komplexen, tiefgehenden Aufgaben (Deep Research, Code-Analyse, Strategie) delegiert Trinity die Aufgabe an Hermes "auf Steroiden". Hermes liefert die Ergebnisse an Trinity zurück, und sie präsentiert sie.

## 2. RAG-Integration (Wissensbasis)
- **Ziel**: Trinity Zugriff auf deine Lehrinhalte geben.
- **Technik**: Integration einer lokalen Vektordatenbank. 
- **Workflow**: 
    1. Skripte werden in einen `/knowledge` Ordner gelegt.
    2. Trinity indiziert diese.
    3. Bei Fragen wie "Was steht dazu in Skript XY?" greift Trinity direkt auf das Wissen zu.

## 3. Dynamische Research-Widgets (Deep Research)
- **Ziel**: On-the-fly Erstellung von Dashboards.
- **Features**:
    - **YouTube**: Automatisches Einbetten relevanter Lehrvideos.
    - **Diagramme**: Nutzung von Chart.js für dynamische Datenvisualisierungen.
    - **Deep Research**: Hermes führt eine Tavily-Suche durch, fasst die Top-Quellen zusammen und baut daraus ein HTML-Dashboard-Widget.

## 5. Plattform-Expansion (Native Apps)
- **Ziel**: Trinity über den Python-Launcher hinaus verfügbar machen.
- **Konzept**: 
    - **macOS App**: Verpackung als native Swift/AppKit Anwendung für bessere Systemintegration und Performance.
    - **iPad App**: Entwicklung einer Begleit-App, die das Dashboard und Trinitys Augen auf das iPad spiegelt (perfekt für das Pult während Mathias im Raum herumläuft).
    - **Sync**: Nahtlose Synchronisation des Wissensstands zwischen Mac und iPad.

## 4. Persona & Rhythmus (Soul-Update) - ✅ IMPLEMENTIERT
- **Ziel**: Maximale Effizienz in der Kommunikation.
- **Umgesetzt**: 
    - Trinity hält sich ab sofort an die **2-3 Sätze** Regel (Brevity).
    - Feedback-Muster ("Einen Moment, Mathias...") ist aktiv.
    - Trinity ist die Chefin, Hermes ist ihr Werkzeug.

---
*Status: Bereit für Umsetzung am Montag.*

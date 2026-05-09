# Skill: RAG Agent

## Beschreibung
Durchsucht die lokale **Wissensbasis** (Vorlesungsskripte, Bücher als PDFs) via semantischer Vektorsuche (Cosine Similarity). Findet die relevantesten Textabschnitte und stellt sie dem LLM als Kontext bereit.

## Trigger-Wörter
`laut skript`, `im skript`, `im buch`, `laut buch`, `wissensbasis`, `rag`, `schlag nach`, `nachschlagen`

## Technologie
- **Embedding-Modell:** `paraphrase-multilingual-MiniLM-L12-v2` (sentence-transformers, lazy geladen)
- **Index:** Vorberechnete Numpy-Embeddings in `RAG/index/`
- **Auto-Rebuild:** Erkennt neue/geänderte PDFs beim Start und baut den Index automatisch neu

## Workflow
1. Trigger erkannt → Embedding der Nutzeranfrage
2. Cosine-Similarity gegen alle Chunks berechnen
3. Top-3 Chunks (Score > 0.3) als Kontext ans LLM übergeben
4. LLM antwortet fachlich korrekt auf Basis der Quellen

## Neue Quellen hinzufügen
Einfach PDF in `RAG/` ablegen → nächster Start rebuildet den Index automatisch.

## Beispiel-Sprachbefehle
- *„Trinity, schlag im Skript nach: Was ist ein Transformer?"*
- *„Trinity, laut Buch, was versteht man unter Prompt Engineering?"*

## Abhängigkeiten
- `sentence-transformers` (Embedding-Modell)
- `numpy` (Vektoroperationen)
- `RAG/build_index.py` (Index-Build)
- `RAG/index/` → chunks.json, embeddings.npy, meta.json

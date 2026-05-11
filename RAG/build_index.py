#!/usr/bin/env python3
"""
RAG Index Builder für Trinity
=============================
Liest alle PDFs im RAG/-Ordner, zerlegt sie in Chunks,
erzeugt Embeddings mit sentence-transformers und speichert
den Index lokal unter RAG/index/.

Nutzung:
    python3 projects/Trinity_Assistant/RAG/build_index.py

Bei neuen PDFs einfach erneut ausführen – der Index wird
komplett neu gebaut.
"""

import os
import json
import numpy as np
import fitz  # PyMuPDF
from sentence_transformers import SentenceTransformer

# Konfiguration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
INDEX_DIR = os.path.join(SCRIPT_DIR, "index")
MEMORY_DIR = os.path.join(PROJECT_DIR, "memory")
CHUNK_SIZE = 500       # Zeichen pro Chunk (kleiner = präziser)
CHUNK_OVERLAP = 100    # Überlappung
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"  # ~120MB, Deutsch-optimiert


def extract_text_from_pdf(pdf_path):
    """Extrahiert sauberen Text aus einer PDF."""
    doc = fitz.open(pdf_path)
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text().strip()
        if text:
            pages.append({"page": i + 1, "text": text})
    doc.close()
    return pages


def extract_text_from_md(md_path):
    """Extrahiert Text aus Markdown-Dateien (Session Summaries)."""
    with open(md_path, "r", encoding="utf-8") as f:
        text = f.read().strip()
    
    # Optional: HTML Tags oder Markdown-Sonderzeichen bereinigen, wenn nötig
    import re
    text = re.sub(r'<[^>]+>', '', text) # HTML Tags entfernen
    
    if text:
        return [{"page": 1, "text": text}]
    return []


def chunk_pages(pages, source_name):
    """Zerlegt Seitentext in überlappende Chunks."""
    chunks = []
    for page_info in pages:
        text = page_info["text"]
        page_num = page_info["page"]
        i = 0
        while i < len(text):
            chunk_text = text[i:i + CHUNK_SIZE].strip()
            if chunk_text and len(chunk_text) > 50:  # Zu kurze Chunks ignorieren
                chunks.append({
                    "source": source_name,
                    "page": page_num,
                    "text": chunk_text
                })
            i += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def build_index():
    """Hauptfunktion: PDFs lesen → Chunks → Embeddings → Speichern."""
    print(f"📚 RAG Index Builder")
    print(f"   Modell: {MODEL_NAME}")
    print(f"   Chunk-Größe: {CHUNK_SIZE} Zeichen (Overlap: {CHUNK_OVERLAP})")
    print()

    # 1. PDFs finden
    pdf_files = [f for f in os.listdir(SCRIPT_DIR) if f.lower().endswith('.pdf')]
    
    # 1.5. MDs (Summaries) aus memory/ finden
    md_files = []
    if os.path.exists(MEMORY_DIR):
        md_files = [f for f in os.listdir(MEMORY_DIR) if f.lower().endswith('.md')]

    if not pdf_files and not md_files:
        print("❌ Keine PDFs im RAG-Ordner und keine MDs im memory-Ordner gefunden!")
        return

    # 2. Text extrahieren und chunken
    all_chunks = []
    
    # PDFs verarbeiten
    for fname in sorted(pdf_files):
        path = os.path.join(SCRIPT_DIR, fname)
        source = fname.replace('.pdf', '')
        print(f"📄 Lese PDF: {fname}...")
        pages = extract_text_from_pdf(path)
        chunks = chunk_pages(pages, source)
        all_chunks.extend(chunks)
        total_chars = sum(len(p["text"]) for p in pages)
        print(f"   → {len(pages)} Seiten, {total_chars:,} Zeichen, {len(chunks)} Chunks")
        
    # MDs verarbeiten
    for fname in sorted(md_files):
        path = os.path.join(MEMORY_DIR, fname)
        source = fname.replace('.md', '')
        print(f"📝 Lese MD: {fname}...")
        pages = extract_text_from_md(path)
        chunks = chunk_pages(pages, source)
        all_chunks.extend(chunks)
        total_chars = sum(len(p["text"]) for p in pages)
        print(f"   → Summary, {total_chars:,} Zeichen, {len(chunks)} Chunks")

    print(f"\n📊 Gesamt: {len(all_chunks)} Chunks aus {len(pdf_files) + len(md_files)} Dokumenten")

    # 3. Embedding-Modell laden
    print(f"\n🤖 Lade Embedding-Modell: {MODEL_NAME}...")
    model = SentenceTransformer(MODEL_NAME)

    # 4. Embeddings erzeugen
    texts = [c["text"] for c in all_chunks]
    print(f"🔢 Erzeuge Embeddings für {len(texts)} Chunks...")
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=64)

    # 5. Speichern
    os.makedirs(INDEX_DIR, exist_ok=True)

    # Chunks als JSON (ohne Text-Duplikate – der Text ist im chunks.json)
    chunks_meta = []
    for c in all_chunks:
        chunks_meta.append({
            "source": c["source"],
            "page": c["page"],
            "text": c["text"]
        })

    chunks_path = os.path.join(INDEX_DIR, "chunks.json")
    with open(chunks_path, "w", encoding="utf-8") as f:
        json.dump(chunks_meta, f, ensure_ascii=False, indent=2)

    embeddings_path = os.path.join(INDEX_DIR, "embeddings.npy")
    np.save(embeddings_path, embeddings)

    # Metadata
    meta = {
        "model": MODEL_NAME,
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "total_chunks": len(all_chunks),
        "sources": list(set(c["source"] for c in all_chunks)),
        "embedding_dim": embeddings.shape[1]
    }
    meta_path = os.path.join(INDEX_DIR, "meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Index gespeichert:")
    print(f"   {chunks_path} ({len(chunks_meta)} Chunks)")
    print(f"   {embeddings_path} ({embeddings.shape})")
    print(f"   {meta_path}")
    print(f"\n🚀 Trinity kann jetzt mit RAG starten!")


if __name__ == "__main__":
    build_index()

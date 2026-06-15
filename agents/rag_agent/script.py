import os
import subprocess
import sys

rag_chunks = []
rag_embeddings = None
rag_model = None
index_loaded = False

def _load_rag_index():
    global rag_chunks, rag_embeddings, index_loaded
    if index_loaded:
        return

    rag_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "RAG")
    index_dir = os.path.join(rag_dir, "index")

    if not os.path.isdir(rag_dir):
        print("📚 RAG-Ordner nicht gefunden, Wissensbasis deaktiviert.")
        index_loaded = True
        return

    # Keine PDFs vorhanden → RAG deaktiviert, kein Fehler
    current_pdfs = sorted([f for f in os.listdir(rag_dir) if f.lower().endswith('.pdf')])
    if not current_pdfs:
        print("📚 RAG: Keine PDFs in RAG/ – Wissensbasis deaktiviert (einfach PDF ablegen zum Aktivieren).")
        index_loaded = True
        return

    needs_rebuild = False
    chunks_path = os.path.join(index_dir, "chunks.json")
    embeddings_path = os.path.join(index_dir, "embeddings.npy")
    meta_path = os.path.join(index_dir, "meta.json")

    if not all(os.path.exists(p) for p in [chunks_path, embeddings_path, meta_path]):
        needs_rebuild = True
    else:
        try:
            import json as _json
            with open(meta_path, "r") as f:
                meta = _json.load(f)
            indexed_sources = sorted(meta.get("sources", []))
            current_sources = sorted([f.replace('.pdf', '') for f in current_pdfs])
            if indexed_sources != current_sources:
                print(f"📚 Neue Dokumente erkannt! Baue Index neu...")
                needs_rebuild = True
            else:
                index_time = os.path.getmtime(embeddings_path)
                for pdf in current_pdfs:
                    if os.path.getmtime(os.path.join(rag_dir, pdf)) > index_time:
                        print(f"📚 {pdf} wurde aktualisiert! Baue Index neu...")
                        needs_rebuild = True
                        break
        except Exception:
            needs_rebuild = True

    if needs_rebuild:
        print("📚 Starte automatischen Index-Build...")
        build_script = os.path.join(rag_dir, "build_index.py")
        if os.path.exists(build_script):
            try:
                result = subprocess.run(
                    [sys.executable, build_script],
                    capture_output=True, text=True, timeout=300
                )
                if result.returncode != 0:
                    print(f"⚠️ Index-Build fehlgeschlagen: {result.stderr[:200]}")
                    index_loaded = True
                    return
            except subprocess.TimeoutExpired:
                print("⚠️ Index-Build Timeout (>5min)")
                index_loaded = True
                return
        else:
            print("⚠️ build_index.py nicht gefunden. Bitte erst ausführen.")
            index_loaded = True
            return

    # Sicherheitscheck: Existiert der Index wirklich nach dem Build?
    if not all(os.path.exists(p) for p in [chunks_path, embeddings_path, meta_path]):
        print("📚 RAG-Index konnte nicht erstellt werden (keine gültigen Inhalte in den PDFs?).")
        index_loaded = True
        return

    try:
        import json as _json
        import numpy as np

        with open(chunks_path, "r", encoding="utf-8") as f:
            rag_chunks = _json.load(f)
        raw_embeddings = np.load(embeddings_path).astype(np.float32)

        norms = np.linalg.norm(raw_embeddings, axis=1, keepdims=True)
        norms = np.maximum(norms, 1e-10)
        rag_embeddings = (raw_embeddings / norms).astype(np.float32)
        rag_embeddings = np.nan_to_num(rag_embeddings, nan=0.0, posinf=0.0, neginf=0.0)

        with open(meta_path, "r") as f:
            meta = _json.load(f)

        sources = meta.get("sources", [])
        print(f"📚 RAG-Index geladen: {len(rag_chunks)} Chunks aus {len(sources)} Dokumenten ({', '.join(sources)})")
        index_loaded = True
    except Exception as e:
        print(f"⚠️ RAG-Index laden fehlgeschlagen: {e}")
        index_loaded = True

def _load_rag_model():
    global rag_model
    if rag_model is not None:
        return True
    try:
        from sentence_transformers import SentenceTransformer
        print("📚 Lade RAG-Modell (erstmalig)...")
        rag_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        print("📚 RAG-Modell geladen ✓")
        return True
    except ImportError:
        print("⚠️ sentence-transformers nicht installiert. RAG-Suche deaktiviert.")
        return False

def can_handle(user_input: str) -> bool:
    triggers = ["laut skript", "im skript", "im buch", "laut buch",
                "wissensbasis", "rag", "schlag nach", "nachschlagen"]
    return any(t in user_input.lower() for t in triggers)

def execute(user_input: str, context: dict = None) -> dict:
    print("📚 RAG-Suche aktiviert...")
    _load_rag_index()
    if not rag_chunks or rag_embeddings is None:
        return {"has_payload": False, "search_context": ""}

    if not _load_rag_model():
        return {"has_payload": False, "search_context": ""}

    import numpy as np
    query_emb = rag_model.encode(user_input, convert_to_numpy=True).astype(np.float32)
    norm = np.linalg.norm(query_emb)
    if norm > 0:
        query_emb /= norm

    similarities = np.dot(rag_embeddings, query_emb)
    indices = np.argsort(similarities)[-3:][::-1]
    
    results = []
    for idx in indices:
        score = float(similarities[idx])
        if score > 0.3:
            chunk = rag_chunks[idx]
            results.append(f"[QUELLE: {chunk['source']}]\n{chunk['text']}")
    
    rag_result = "\n\n".join(results)[:2000]
    
    if rag_result:
        rag_context = (
            f"--- RELEVANTE LEHRINHALTE (aus deiner Wissensbasis) ---\n"
            f"Nutze folgende Auszüge aus den Vorlesungsskripten/Büchern, "
            f"um fachlich korrekt zu antworten:\n\n{rag_result}\n\n"
        )
        return {"has_payload": False, "search_context": rag_context}
    
    return {"has_payload": False, "search_context": ""}

def init():
    _load_rag_index()

import os
import time
import glob
import subprocess
import sys

def can_handle(query: str) -> bool:
    router_text = query.lower()
    return any(phrase in router_text for phrase in [
        "session beenden", "session abschließen", 
        "zusammenfassung der letzten session", "letzte session zusammenfassen",
        "letzte sitzung zusammenfassen", "session zusammenfassen"
    ])

def execute(query: str, context: dict = None) -> dict:
    if not context or "brain" not in context:
        return {"has_payload": False, "html_payload": "", "search_context": ""}
        
    brain = context["brain"]
    router_text = query.lower()
    
    # Pfade definieren
    project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    memory_dir = os.path.join(project_dir, "memory")
    summaries_dir = os.path.join(memory_dir, "summaries")
    os.makedirs(summaries_dir, exist_ok=True)
    
    # 1. Welche Datei soll zusammengefasst werden?
    transcript_file = context.get("transcript_file")
    
    # Falls "letzte Session" gefragt wurde oder die aktuelle Datei fast leer ist
    is_last_session_request = "letzte" in router_text
    
    if is_last_session_request or not transcript_file or not os.path.exists(transcript_file) or os.path.getsize(transcript_file) < 100:
        # Finde die neueste Sitzung im memory-Ordner (Sitzung_*.md)
        session_files = glob.glob(os.path.join(memory_dir, "Sitzung_*.md"))
        if session_files:
            # Sortiere nach Zeitstempel im Namen oder Änderungsdatum
            session_files.sort(key=os.path.getmtime, reverse=True)
            # Wenn wir im "letzte Session" Modus sind, nehmen wir die zweitneueste, falls die aktuelle gerade offen ist
            if is_last_session_request and len(session_files) > 1:
                transcript_file = session_files[1]
            else:
                transcript_file = session_files[0]
            print(f"📄 Nutze vorherige Session für Summary: {os.path.basename(transcript_file)}")
        else:
            return {
                "has_payload": False, 
                "html_payload": "", 
                "search_context": "Ich konnte keine vergangenen Sitzungen zum Zusammenfassen finden."
            }

    # 2. Transkript lesen
    try:
        with open(transcript_file, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return {"has_payload": False, "html_payload": "", "search_context": f"Fehler beim Lesen: {e}"}

    print(f"📊 Generiere Abschluss-Zusammenfassung für: {os.path.basename(transcript_file)}")
    
    prompt = build_summary_prompt(content)
    
    summary = brain.ask_llm([{"role": "user", "content": prompt}])
    
    if not summary:
        return {"has_payload": False, "html_payload": "", "search_context": "Die KI konnte keine Zusammenfassung generieren."}

    # 3. Speichern
    file_basename = os.path.basename(transcript_file).replace(".md", "")
    summary_filename = f"Summary_{file_basename}.md"
    summary_path = os.path.join(summaries_dir, summary_filename)
    
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(f"# Session Summary – {file_basename}\n\n")
        f.write(summary)
    
    print(f"✅ Summary gespeichert: {summary_path}")

    memory_id = ""
    try:
        from memory_store import MemoryStore
        from tenant_context import tenant_memory_db_path

        project_dir_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        tenant_id = str(context.get("tenant_id") or "").strip()
        store = MemoryStore(
            str(tenant_memory_db_path(project_dir_path, tenant_id))
            if tenant_id
            else None
        )
        session_id = str(context.get("session_id") or file_basename).strip()
        session_name = str(context.get("session_name") or file_basename).strip()
        store.ensure_session(session_id, session_name or "Trinity Session")
        memory_id = store.remember(
            summary,
            tags=["session", "summary", "vorlesung", "trinity"],
            kind="session-summary",
            source="session-summary-agent",
            session_id=session_id,
            weight=0.82,
            baked=True,
            metadata={
                "summary_path": summary_path,
                "transcript_file": transcript_file,
                "session_name": session_name,
            },
        )
    except Exception as exc:  # pylint: disable=broad-except
        print(f"⚠️ Summary-Memory konnte nicht gespeichert werden: {exc}")

    try:
        config_path = os.path.join(project_dir, "core", "config.json")
        import json
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as handle:
                config = json.load(handle)
            proactive = config.get("proactive", {})
            if proactive.get("session_summary_auto_rag_indexing", True):
                rag_script = os.path.join(project_dir, "RAG", "build_index.py")
                subprocess.Popen([sys.executable, rag_script], cwd=project_dir)
                print("🚀 Auto-RAG: Reindex für Session-Summary gestartet.")
    except Exception as exc:  # pylint: disable=broad-except
        print(f"⚠️ Auto-RAG konnte nicht gestartet werden: {exc}")

    # 4. HTML Payload erstellen (Editierbar)
    formatted_summary = summary.replace('\n', '<br>')
    html_payload = f"""
    <!-- KEEP_OPEN -->
    <!-- SESSION_SUMMARY_PAYLOAD -->
    <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.2); padding-bottom: 10px; margin-bottom: 15px;">
        <h2 style="margin: 0; font-weight: 300; font-size: 18px;">📋 Abschluss-Zusammenfassung</h2>
        <span style="font-size: 12px; opacity: 0.5;">Datei: {summary_filename}</span>
    </div>
    
    <div style="font-size: 15px; line-height: 1.6; opacity: 0.9; margin-bottom: 20px;">
        {formatted_summary}
    </div>
    
    <div style="border-top: 1px dashed rgba(255,255,255,0.3); padding-top: 15px;">
        <h3 style="font-size: 14px; font-weight: bold; margin-bottom: 10px; color: #00e5ff;">✍️ Eigene Ergänzungen:</h3>
        <textarea id="user_notes" style="width: 100%; height: 120px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; color: white; padding: 10px; font-family: inherit; font-size: 14px; outline: none;" placeholder="Schreibe hier weitere Notizen hinein..."></textarea>
        <p style="font-size: 11px; opacity: 0.5; margin-top: 5px;">
            Hinweis: Ergänzungen in diesem Fenster sind temporär. Für dauerhafte Änderungen editiere bitte die Datei direkt in <code>memory/summaries/</code>.
        </p>
    </div>
    """
    
    search_context = f"--- SESSION SUMMARY ---\nIch habe die Session '{file_basename}' zusammengefasst und als {summary_filename} gespeichert. Du kannst sie dir jetzt ansehen und ggf. Notizen ergänzen."
    
    return {
        "has_payload": True,
        "html_payload": html_payload,
        "search_context": search_context,
        "summary": summary,
        "summary_path": summary_path,
        "memory_id": memory_id,
        "transcript_file": transcript_file,
        "summary_filename": summary_filename,
    }


def build_summary_prompt(content: str) -> str:
    return (
        "Du bist ein professioneller Protokollant. Erstelle eine strukturierte "
        "Zusammenfassung der folgenden Trinity-Session.\n\n"
        "Extrahiere diese Abschnitte:\n"
        "1. Hauptthemen\n"
        "2. Key-Takeaways\n"
        "3. Entscheidungen oder konkrete Ergebnisse\n"
        "4. Offene Fragen / To-Dos\n"
        "5. Relevante erzeugte Artefakte oder Medien, falls im Verlauf genannt\n\n"
        f"Hier ist das Transkript:\n---\n{content}\n---\n"
        "Antworte auf Deutsch im Markdown-Format."
    )

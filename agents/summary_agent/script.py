import os

def can_handle(query: str) -> bool:
    router_text = query.lower()
    return any(phrase in router_text for phrase in [
        "big picture", "big-picture", "überblick der vorlesung", "überblick der sitzung",
        "zusammenfassung der vorlesung", "zusammenfassung der heutigen",
        "infografik der vorlesung", "infografik der sitzung",
        "visualisiere die vorlesung"
    ])

def execute(query: str, context: dict = None) -> dict:
    if not context or "brain" not in context:
        return {"has_payload": False, "html_payload": "", "search_context": ""}
        
    brain = context["brain"]
    
    print(f"📊 Erstelle Zusammenfassung der Sitzung...")
    transcript_file = "memory/test.md" # Default
    transcript = brain.read_transcript(transcript_file)
    
    prompt = (
        f"Fasse die bisherige Vorlesungssitzung basierend auf diesem Transkript zusammen:\n"
        f"{transcript[:3000]}\n\n"
        f"Antworte auf Deutsch, strukturiert mit Bullet-Points."
    )
    summary = brain.ask_llm([{"role": "user", "content": prompt}])
    
    if summary:
        paragraphs = [p.strip() for p in summary.split('\n') if p.strip()]
        formatted_summary = "".join([f"<p style='margin-bottom:15px; line-height:1.5;'>{p}</p>" for p in paragraphs])
        html_payload = f"<!-- KEEP_OPEN --><h2>📊 Sitzungs-Überblick</h2><div style='font-size:15px; opacity:0.9;'>{formatted_summary}</div>"
        
        search_context = "--- SUMMARY ---\nDu hast eine Zusammenfassung der Sitzung erstellt. Erkläre dem Nutzer kurz die wichtigsten Punkte.\n\n"
        
        return {
            "has_payload": True,
            "html_payload": html_payload,
            "search_context": search_context
        }
    
    return {"has_payload": False, "html_payload": "", "search_context": ""}

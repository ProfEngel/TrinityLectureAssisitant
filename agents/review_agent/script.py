import os

def can_handle(query: str) -> bool:
    router_text = query.lower()
    return any(phrase in router_text for phrase in [
        "review", "letzte sitzung", "letzte vorlesung", "zusammenfassung der letzten"
    ])

def execute(query: str, context: dict = None) -> dict:
    # Hier könnte man die memory/ test.md oder ein echtes Summary-File der letzten Session laden
    search_context = "--- AGENTIC ACTION ---\nDu liest jetzt einen kurzen Review der letzten Session vor. Greife auf dein Wissen zurück oder verweise darauf, dass die letzte Session-Zusammenfassung noch geladen werden muss.\n\n"
    
    html_payload = """
    <!-- KEEP_OPEN -->
    <h2 style="margin-top: 0; font-weight: 300; border-bottom: 1px solid rgba(255,255,255,0.2); padding-bottom: 10px; font-size: 18px;">🔄 Review-Modus</h2>
    <div style="font-size: 13px; opacity: 0.7; margin-bottom: 10px;">Lade Zusammenfassung der letzten Vorlesung...</div>
    """
    
    return {"has_payload": True, "html_payload": html_payload, "search_context": search_context}

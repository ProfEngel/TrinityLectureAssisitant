import os

def can_handle(query: str) -> bool:
    router_text = query.lower()
    return any(phrase in router_text for phrase in [
        "bitte nicht zuhören", "hör weg", "fokus", "weiter geht's", "hör wieder zu"
    ])

def execute(query: str, context: dict = None) -> dict:
    router_text = query.lower()
    
    if "weiter geht's" in router_text or "hör wieder zu" in router_text:
        # Hier könnte man künftig ein Flag in transcriber.py umstellen
        search_context = "--- AGENTIC ACTION ---\nDu bist nun wieder im aktiven Zuhör-Modus. Begrüße den Nutzer kurz zurück.\n\n"
        return {"has_payload": False, "html_payload": "", "search_context": search_context}
    else:
        # Fokus-Modus aktivieren
        search_context = "--- AGENTIC ACTION ---\nDu gehst jetzt in den passiven Fokus-Modus und hörst vorerst nicht mehr zu. Bestätige dies ganz kurz.\n\n"
        return {"has_payload": False, "html_payload": "", "search_context": search_context}

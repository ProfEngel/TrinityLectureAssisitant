import re

def can_handle(query: str) -> bool:
    """
    Prüft, ob die Anfrage einen Maps-Befehl enthält.
    """
    router_text = query.lower()
    return any(word in router_text for word in ["route", "karte", "navigiere", "maps"])

def execute(query: str, context: dict = None) -> dict:
    """
    Führt die Maps-Logik aus und liefert Payload sowie Suchkontext zurück.
    """
    lower_query = query.lower()
    
    # Versuche das Ziel zu finden
    destination = query.replace("Trinity", "").replace("trinity", "").replace("zeig", "").replace("mir", "").replace("die", "").strip()
    match = re.search(r'(?:nach|zu|in)\s+([A-Za-zäöüÄÖÜß]+)', lower_query)
    if match:
        destination = match.group(1).title()
        
    html_payload = f"""
    <!-- KEEP_OPEN -->
    <h2 style="margin-top: 0; font-weight: 300; border-bottom: 1px solid rgba(255,255,255,0.2); padding-bottom: 10px; font-size: 18px;">Karte: {destination}</h2>
    <div style="width: 100%; height: 320px; border-radius: 15px; overflow: hidden; margin-top: 15px;">
        <iframe 
            width="100%" 
            height="100%" 
            frameborder="0" 
            style="border:0" 
            src="https://www.google.com/maps?q={destination}&output=embed" 
            allowfullscreen>
        </iframe>
    </div>
    """
    
    search_context = f"--- AGENTIC ACTION ---\nDu hast soeben erfolgreich eine interaktive Google Maps Karte für '{destination}' im UI eingeblendet. Bestätige dem Nutzer kurz, dass die Karte jetzt im Nebenfenster geöffnet ist.\n\n"
    
    return {
        "has_payload": True,
        "html_payload": html_payload,
        "search_context": search_context
    }

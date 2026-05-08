import os

def can_handle(query: str) -> bool:
    router_text = query.lower()
    return any(word in router_text for word in [
        "nächste folie", "nächstes bild", "weiter", 
        "vorherige folie", "zurück", "präsentation starten", "präsentation beenden"
    ]) and ("folie" in router_text or "präsentation" in router_text or "weiter" in router_text or "zurück" in router_text)

def execute(query: str, context: dict = None) -> dict:
    router_text = query.lower()
    command = None
    action_text = ""

    if "präsentation starten" in router_text:
        command = 'tell application "Microsoft PowerPoint" to run slide show slide show settings of active presentation'
        action_text = "Präsentation gestartet."
    elif "beenden" in router_text and ("präsentation" in router_text or "folie" in router_text):
        command = 'tell application "Microsoft PowerPoint" to exit slide show slide show view of slide show window 1'
        action_text = "Präsentation beendet."
    elif "zurück" in router_text or "vorherige" in router_text:
        command = 'tell application "Microsoft PowerPoint" to go to previous slide slide show view of slide show window 1'
        action_text = "Zurück zur vorherigen Folie."
    elif "weiter" in router_text or "nächste" in router_text:
        command = 'tell application "Microsoft PowerPoint" to go to next slide slide show view of slide show window 1'
        action_text = "Zur nächsten Folie gewechselt."

    if command:
        print(f"🎬 PowerPoint Action: {action_text}")
        try:
            os.system(f"osascript -e '{command}'")
        except Exception as e:
            print(f"⚠️ Fehler bei PowerPoint-Steuerung: {e}")
        
        search_context = f"--- AGENTIC ACTION ---\nDu hast soeben PowerPoint gesteuert: {action_text} Bestätige dies kurz.\n\n"
        return {"has_payload": False, "html_payload": "", "search_context": search_context}
    
    return {"has_payload": False, "html_payload": "", "search_context": ""}

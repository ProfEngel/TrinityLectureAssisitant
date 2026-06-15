import os
import sys


CORE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "core",
)
if CORE_DIR not in sys.path:
    sys.path.insert(0, CORE_DIR)

from platform_adapters.powerpoint import create_powerpoint_controller


REQUIRED_CAPABILITIES = {"powerpoint_automation"}

ACTION_TEXT = {
    "start": "Präsentation gestartet.",
    "stop": "Präsentation beendet.",
    "previous": "Zurück zur vorherigen Folie.",
    "next": "Zur nächsten Folie gewechselt.",
}

def can_handle(query: str) -> bool:
    router_text = query.lower()
    return any(word in router_text for word in [
        "nächste folie", "nächstes bild", "weiter", 
        "vorherige folie", "zurück", "präsentation starten", "präsentation beenden"
    ]) and ("folie" in router_text or "präsentation" in router_text or "weiter" in router_text or "zurück" in router_text)

def execute(query: str, context: dict = None) -> dict:
    router_text = query.lower()
    action = None

    if "präsentation starten" in router_text:
        action = "start"
    elif "beenden" in router_text and ("präsentation" in router_text or "folie" in router_text):
        action = "stop"
    elif "zurück" in router_text or "vorherige" in router_text:
        action = "previous"
    elif "weiter" in router_text or "nächste" in router_text:
        action = "next"

    if action:
        action_text = ACTION_TEXT[action]
        print(f"🎬 PowerPoint Action: {action_text}")
        ok, error = create_powerpoint_controller().perform(action)
        if not ok:
            print(f"⚠️ Fehler bei PowerPoint-Steuerung: {error}")
            return {
                "has_payload": False,
                "html_payload": "",
                "search_context": (
                    "--- POWERPOINT FEHLER ---\n"
                    f"PowerPoint konnte nicht gesteuert werden: {error}\n\n"
                ),
            }

        search_context = (
            "--- AGENTIC ACTION ---\n"
            f"Du hast soeben PowerPoint gesteuert: {action_text} "
            "Bestätige dies kurz.\n\n"
        )
        return {
            "has_payload": False,
            "html_payload": "",
            "search_context": search_context,
        }
    
    return {"has_payload": False, "html_payload": "", "search_context": ""}

import os
import sys
import subprocess

def can_handle(query: str) -> bool:
    router_text = query.lower()
    return any(phrase in router_text for phrase in [
        "öffne einstellungen", "konfiguration öffnen", "settings öffnen",
        "einstellungen öffnen", "konfiguration anzeigen"
    ])

def execute(query: str, context: dict = None) -> dict:
    search_context = "--- AGENTIC ACTION ---\nDu hast soeben die Einstellungen geöffnet. Bestätige dem Nutzer kurz, dass sich das Konfigurationsfenster jetzt öffnet.\n\n"
    
    # Pfad zum settings_ui.py
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    settings_script = os.path.join(base_dir, "core", "settings_ui.py")
    
    # Asynchron ausführen, damit Trinity nicht blockiert
    subprocess.Popen([sys.executable, settings_script])
    
    return {"has_payload": False, "html_payload": "", "search_context": search_context}

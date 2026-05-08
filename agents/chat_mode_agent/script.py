import os

def can_handle(query: str) -> bool:
    router_text = query.lower()
    return any(phrase in router_text for phrase in [
        "lass uns quatschen", "chat modus", "chat-modus", "gesprächsmodus"
    ])

def execute(query: str, context: dict = None) -> dict:
    search_context = "--- AGENTIC ACTION ---\nDu bist nun im Natural Conversation Mode (Chat-Modus). Antworte ab sofort extrem kurz und gesprächig, als würdest du mit dem Nutzer locker plaudern.\n\n"
    return {"has_payload": False, "html_payload": "", "search_context": search_context}

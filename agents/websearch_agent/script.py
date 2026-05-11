from datetime import datetime

def can_handle(query: str) -> bool:
    router_text = query.lower()
    return any(word in router_text for word in ["recherchier", "such ", "suche ", "finde heraus", "nächste spiel", "nächstes spiel", "spielplan", "nachricht", "online", "aktuell", "heute", "heutige", "neuigkeiten", "news", "gerade los"])

def execute(query: str, context: dict = None) -> dict:
    if not context or "brain" not in context:
        return {"has_payload": False, "html_payload": "", "search_context": ""}
        
    brain = context["brain"]
    
    if not brain.tavily_key or not str(brain.tavily_key).strip():
        search_context = "--- INFO ---\nDer Nutzer hat um eine Websuche gebeten, aber in der Konfiguration ist kein Tavily API-Key hinterlegt. Bitte weise den Nutzer freundlich darauf hin, dass er den Key erst in den Einstellungen eintragen muss (Tipp: 'Trinity, öffne Einstellungen').\n\n"
        return {"has_payload": False, "html_payload": "", "search_context": search_context}
        
    # Aktuelles Datum für zeitliche Einordnung
    now = datetime.now()
    timestamp = now.strftime("%A, %d. %B %Y, %H:%M Uhr")
    date_iso = now.strftime("%Y-%m-%d")
    
    # Aus dem vollen Kontext die eigentliche Suchanfrage extrahieren
    search_query = brain.ask_llm([{"role": "user", "content": 
        f"Heute ist {timestamp}.\n"
        f"Der Nutzer hat folgendes gesagt: '{query}'\n"
        f"Extrahiere daraus die EINE Suchanfrage für eine Web-Suchmaschine.\n"
        f"Antworte NUR mit dem Suchbegriff (max 8 Wörter, keine Erklärung)."
    }]).strip('" \n.')
    print(f"🔎 Extrahierte Suchanfrage: '{search_query}'")

    if len(search_query) < 3:
        search_context = "--- AGENTIC ACTION ---\nDie Suchanfrage war unklar. Bitte den Nutzer, das Thema genauer zu benennen.\n\n"
        return {"has_payload": False, "html_payload": "", "search_context": search_context}

    results = _search_tavily(search_query, brain.tavily_key)
    if results:
        print(f"✅ Tavily: {len(results)} Ergebnisse gefunden")
        search_results_text = "\n".join([f"- {r['title']}: {r['content']}" for r in results])
        search_context = (
            f"--- AKTUELLE WEB-RECHERCHE (ECHTZEIT-DATEN) ---\n"
            f"HEUTIGES DATUM: {timestamp} (ISO: {date_iso})\n"
            f"Suchanfrage: '{search_query}'\n"
            f"Die Web-Suche lieferte folgende frische Fakten. Diese sind aktueller als dein Training. "
            f"Nutze AUSSCHLIESSLICH diese Daten – ignoriere dein internes Wissen zu diesem Thema. "
            f"Beachte das heutige Datum, um korrekt zu bestimmen, welche Ereignisse in der Zukunft liegen:\n"
            f"{search_results_text}\n\n"
        )
        
        # Payload für das UI-Dashboard erstellen
        html_items = "".join([f"<div style='margin-bottom:20px;'><a href='{r.get('url','')}' style='color:#00bfff; font-weight:bold;'>{r['title']}</a><div style='font-size:15px; opacity:0.9; margin-top:5px; line-height:1.4;'>{r['content']}</div></div>" for r in results])
        html_payload = f"<h2 style='margin-top: 0; font-weight: 300; border-bottom: 1px solid rgba(255,255,255,0.2); padding-bottom: 10px; font-size: 18px;'>🔍 {search_query}</h2><div style='padding-top:10px;'>{html_items}</div>"
        
        return {
            "has_payload": True,
            "html_payload": html_payload,
            "search_context": search_context
        }
    else:
        search_context = "--- AGENTIC ACTION ---\nDie Web-Suche ergab keine Ergebnisse. Informiere den Nutzer darüber und biete an, mit anderen Begriffen zu suchen.\n\n"
        return {"has_payload": False, "html_payload": "", "search_context": search_context}

def _search_tavily(query, api_key):
    import requests
    if not api_key:
        print("⚠️ Warnung: Tavily API-Key fehlt in config.json")
        return []
    
    url = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "advanced",
        "include_answer": False,
        "include_images": False,
        "include_raw_content": False,
        "max_results": 3
    }
    
    try:
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        return data.get("results", [])
    except Exception as e:
        print(f"⚠️ Fehler bei Tavily Suche: {e}")
        return []

import re
import urllib.parse
import requests
import json
import os
import time
from bs4 import BeautifulSoup

def can_handle(query: str) -> bool:
    """
    Prüft, ob die Anfrage eine tiefe Recherche verlangt.
    """
    router_text = query.lower()
    trigger_words = [
        "deep research", "deep-research", "tiefenrecherche", "tiefen-recherche",
        "tiefgründige recherche", "intensive recherche", "recherchiere intensiv",
        "deepresearch", "deep search", "deep-search"
    ]
    return any(word in router_text for word in trigger_words)

def execute(query: str, context: dict = None) -> dict:
    """
    Führt den Local Deep Research Agentic Loop aus.
    """
    if not context or "brain" not in context:
        return {"has_payload": False, "html_payload": "", "search_context": ""}
        
    brain = context["brain"]
    
    print("\n🕵️‍♂️ [Deep Research] Agent gestartet...")
    print(f"🎯 Ziel-Thema: '{query}'")
    
    # ── PHASE 1: Suchanfragen generieren ─────────────────────────────────────
    print("🔎 [Phase 1/5] Generiere strategische Suchanfragen via LLM...")
    prompt_q = [
        {"role": "system", "content": "Du bist der Suchstrategie-Kern eines Deep-Research-Agenten. Deine Aufgabe ist es, für ein gegebenes Thema 3 verschiedene, hochgradig präzise und komplementäre Suchanfragen (jeweils max 6 Wörter) zu erstellen, um das Thema aus verschiedenen Blickwinkeln im Web zu erforschen. Antworte AUSSCHLIESSLICH im Format:\n1. [Suchanfrage 1]\n2. [Suchanfrage 2]\n3. [Suchanfrage 3]"},
        {"role": "user", "content": f"Thema: {query}"}
    ]
    raw_queries = brain.ask_llm(prompt_q)
    queries = []
    for line in raw_queries.split("\n"):
        match = re.search(r'\d+\.\s*(.*)', line)
        if match:
            queries.append(match.group(1).strip('" \n.'))
            
    # Fallback, falls LLM-Formatierung schiefgeht
    if len(queries) < 3:
        queries = [query, f"{query} details", f"{query} analysis"]
        
    print("   Generierte Suchanfragen:")
    for idx, q in enumerate(queries):
        print(f"    -> Query {idx+1}: '{q}'")
        
    # ── PHASE 2: Websuche & Scraping ─────────────────────────────────────────
    print("🌐 [Phase 2/5] Durchsuche das Web & Scrape Inhalte...")
    scraped_data = []
    visited_urls = set()
    
    for q in queries:
        print(f"   🔎 Suche nach: '{q}'...")
        search_results = _search_ddg(q, max_results=3)
        
        for r in search_results:
            url = r['url']
            if url in visited_urls:
                continue
            visited_urls.add(url)
            
            print(f"      📄 Scrape: {url[:60]}...")
            page_text = _scrape_page(url)
            if page_text:
                scraped_data.append({
                    "title": r['title'],
                    "url": url,
                    "content": page_text
                })
            else:
                # Fallback auf Snippet, falls Scraping fehlschlägt
                scraped_data.append({
                    "title": r['title'],
                    "url": url,
                    "content": r['content']
                })
                
    # ── PHASE 3: Lücken-Analyse & Folge-Suchen ───────────────────────────────
    print("🧠 [Phase 3/5] Analysiere gesammelte Informationen auf Wissenslücken...")
    # Zusammenfassung der bisherigen Funde für das LLM
    context_summary = ""
    for idx, sd in enumerate(scraped_data[:6]):
        context_summary += f"Quelle [{idx+1}]: {sd['title']} ({sd['url']})\nInhalt (Auszug): {sd['content'][:800]}\n\n"
        
    prompt_gap = [
        {"role": "system", "content": "Du bist der Analyse-Kern eines Deep-Research-Agenten. Basierend auf den bisher gesammelten Web-Ergebnissen sollst du 2 präzise Folge-Suchanfragen (max 6 Wörter) generieren, um offene Fragen oder tiefergehende Lücken zu schließen. Antworte AUSSCHLIESSLICH im Format:\n1. [Folge-Suchanfrage 1]\n2. [Folge-Suchanfrage 2]"},
        {"role": "user", "content": f"Ziel-Thema: {query}\n\nBisherige Quellen & Funde:\n{context_summary}"}
    ]
    raw_gaps = brain.ask_llm(prompt_gap)
    gap_queries = []
    for line in raw_gaps.split("\n"):
        match = re.search(r'\d+\.\s*(.*)', line)
        if match:
            gap_queries.append(match.group(1).strip('" \n.'))
            
    if len(gap_queries) < 2:
        gap_queries = [f"{query} advanced", f"{query} future research"]
        
    print("   Erkannte Lücken-Suchanfragen:")
    for idx, gq in enumerate(gap_queries):
        print(f"    -> Folge-Query {idx+1}: '{gq}'")
        
    # ── PHASE 4: Tiefensuche (Second-Phase) ──────────────────────────────────
    print("🌐 [Phase 4/5] Führe Tiefensuchen & Scraping durch...")
    for gq in gap_queries:
        print(f"   🔎 Suche nach: '{gq}'...")
        search_results = _search_ddg(gq, max_results=2)
        for r in search_results:
            url = r['url']
            if url in visited_urls:
                continue
            visited_urls.add(url)
            
            print(f"      📄 Scrape: {url[:60]}...")
            page_text = _scrape_page(url)
            if page_text:
                scraped_data.append({
                    "title": r['title'],
                    "url": url,
                    "content": page_text
                })
            else:
                scraped_data.append({
                    "title": r['title'],
                    "url": url,
                    "content": r['content']
                })

    # ── PHASE 5: Finaler Report-Synthese ────────────────────────────────────
    print("📝 [Phase 5/5] Synthetisiere finalen, akademischen Report...")
    
    # Gesamten gesammelten Datenpool strukturieren
    final_pool = ""
    for idx, sd in enumerate(scraped_data):
        final_pool += f"Quelle [{idx+1}]: {sd['title']}\nURL: {sd['url']}\nInhalt:\n{sd['content']}\n"
        final_pool += "="*40 + "\n\n"
        
    prompt_report = [
        {"role": "system", "content": (
            "Du bist ein Elite-Wissenschaftler und Chef-Analyst. Deine Aufgabe ist es, aus dem zur Verfügung gestellten Datenpool einen majestätischen, akademisch fundierten und tiefgründigen Research-Report zu schreiben. Der Report MUSS extrem ausführlich sein (mehrere Kapitel) und im perfekten GitHub-Flavored-Markdown verfasst werden.\n\n"
            "STRUKTUR-REGELN:\n"
            "- Dynamischer, professioneller Titel (H1)\n"
            "- Inhaltsverzeichnis (TOC)\n"
            "- Kapitel 1: Management Summary\n"
            "- Kapitel 2: Fundamentale Grundlagen & Hintergrund\n"
            "- Kapitel 3: Detaillierte Analyse & Technische Spezifikationen (nutze Tabellen oder Listen für Vergleiche, falls passend)\n"
            "- Kapitel 4: Zukünftige Entwicklung & Implikationen\n"
            "- Kapitel 5: Quellenverzeichnis (Nummerierte Citations wie [1], [2], die direkt auf die angegebenen Quell-URLs verlinken)\n\n"
            "WICHTIG: Referenziere Behauptungen im Fließtext konsequent mit den Nummern der Quellen (z.B. '[1]', '[2]')!"
        )},
        {"role": "user", "content": f"Ziel-Thema: {query}\n\nGesamter gesammelter Datenpool:\n{final_pool[:12000]}"} # Token-Limit-Sicherheit
    ]
    
    report_markdown = brain.ask_llm(prompt_report)
    
    # Markdown in schönes HTML für die QWebEngineView umwandeln
    html_payload = _render_report_to_html(query, report_markdown, list(visited_urls))
    
    print("✅ Deep Research abgeschlossen!")
    
    # Kurzer Sprach-Bestätigungskontext für das LLM
    search_context = (
        f"--- AGENTIC ACTION: DEEP RESEARCH ABGESCHLOSSEN ---\n"
        f"Du hast eine extrem tiefgründige, mehrstufige Web-Recherche zum Thema '{query}' durchgeführt.\n"
        f"Ein majestätischer, mehrseitiger wissenschaftlicher Report wurde BEREITS im Nebenfenster eingeblendet.\n"
        f"DEINE AUFGABE JETZT: Sag dem Nutzer in 1-2 kurzen, begeisterten und professionellen Sätzen auf Deutsch, "
        f"dass deine Tiefenrecherche abgeschlossen ist und der detaillierte Report im Dashboard bereitsteht.\n"
        f"Beispiel: 'Ich habe eine umfassende Tiefenrecherche für dich durchgeführt, Mathias. Der mehrseitige akademische Report mit allen Quellen steht jetzt in deinem Dashboard bereit.'\n"
        f"VERBOTEN: Markdown, Listen, Tabellen, technische Erklärungen, Zusammenfassungen, Quelllinks.\n\n"
    )
    
    return {
        "has_payload": True,
        "html_payload": html_payload,
        "search_context": search_context
    }

def _search_ddg(query: str, max_results: int = 5) -> list:
    """
    Führt eine DuckDuckGo-Suche über das plain HTML-Interface durch.
    """
    results = []
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            for div in soup.find_all('div', class_='web-result'):
                title_el = div.find('a', class_='result__a')
                snippet_el = div.find('a', class_='result__snippet')
                if title_el and snippet_el:
                    link = title_el['href']
                    if "uddg=" in link:
                        parsed = urllib.parse.urlparse(link)
                        queries = urllib.parse.parse_qs(parsed.query)
                        if "uddg" in queries:
                            link = queries["uddg"][0]
                            
                    results.append({
                        'title': title_el.text.strip(),
                        'url': link,
                        'content': snippet_el.text.strip()
                    })
                    if len(results) >= max_results:
                        break
    except Exception as e:
        print(f"⚠️ DuckDuckGo Fehler für '{query}': {e}")
    return results

def _scrape_page(url: str) -> str:
    """
    Scrapt und säubert den Inhalt einer Webseite.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        r = requests.get(url, headers=headers, timeout=8)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            # Strippe irrelevante Elemente
            for tag in soup(["script", "style", "nav", "header", "footer", "form", "aside", "noscript"]):
                tag.decompose()
            
            # Textblöcke extrahieren
            text_blocks = []
            for el in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'li']):
                txt = el.text.strip()
                if len(txt) > 25:
                    text_blocks.append(txt)
            
            full_text = "\n".join(text_blocks)
            return full_text[:4000] # Cap auf 4k Zeichen für Context-Verdaulichkeit
    except Exception as e:
        print(f"⚠️ Scraping Fehler für '{url}': {e}")
    return ""

def _render_report_to_html(topic: str, markdown: str, urls: list) -> str:
    """
    Konvertiert das Report-Markdown in edles, glasmorphisches HTML.
    """
    # Sehr simpler Markdown -> HTML Konverter für den Fall, dass kein markdown-Package installiert ist
    html = markdown
    
    # Headers
    html = re.sub(r'^#\s+(.*?)$', r'<h1 style="color:#58a6ff; font-weight:300; border-bottom:1px solid rgba(255,255,255,0.2); padding-bottom:10px; font-size:24px; margin-top:25px; margin-bottom:15px;">\1</h1>', html, flags=re.MULTILINE)
    html = re.sub(r'^##\s+(.*?)$', r'<h2 style="color:#8b949e; font-weight:400; font-size:18px; margin-top:20px; margin-bottom:10px; border-bottom: 1px solid rgba(255,255,255,0.05); padding-bottom:5px;">\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^###\s+(.*?)$', r'<h3 style="color:#e6edf3; font-weight:500; font-size:15px; margin-top:15px; margin-bottom:5px;">\1</h3>', html, flags=re.MULTILINE)
    
    # Bold / Italic
    html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'\*(.*?)\*', r'<em>\1</em>', html)
    
    # Citations in links umwandeln
    # Format: [1], [2] -> verlinkte Hochzahlen
    for i in range(1, 30):
        if i <= len(urls):
            target_url = urls[i-1]
            html = html.replace(f"[{i}]", f'<a href="{target_url}" target="_blank" style="color:#58a6ff; text-decoration:none; font-weight:bold; font-size:85%; vertical-align:super;">[{i}]</a>')
            
    # Neue Zeilen in Absätze umwandeln
    paragraphs = []
    for block in html.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        if block.startswith("<h") or block.startswith("<ul>") or block.startswith("<li>") or block.startswith("<table"):
            paragraphs.append(block)
        else:
            # Bulletpoints
            if block.startswith("- ") or block.startswith("* "):
                lines = block.split("\n")
                ul_items = ""
                for line in lines:
                    line_clean = re.sub(r'^[-*]\s+', '', line.strip())
                    ul_items += f'<li style="margin-bottom:6px; line-height:1.4;">{line_clean}</li>'
                paragraphs.append(f'<ul style="margin-left:20px; margin-bottom:15px;">{ul_items}</ul>')
            else:
                paragraphs.append(f'<p style="margin-bottom:15px; line-height:1.6; opacity:0.95; font-size:14px; text-align:justify;">{block}</p>')
                
    body_content = "\n".join(paragraphs)
    
    html_payload = f"""
    <!-- KEEP_OPEN -->
    <div style="font-family:'Inter', sans-serif; color:#e6edf3;">
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:10px; opacity:0.6; font-size:11px;">
            <span>🕵️‍♂️ LOCAL DEEP RESEARCH REPORT</span>
            <span>·</span>
            <span>{time.strftime("%d. %B %Y")}</span>
        </div>
        <div style="padding-right: 5px;">
            {body_content}
        </div>
    </div>
    """
    return html_payload

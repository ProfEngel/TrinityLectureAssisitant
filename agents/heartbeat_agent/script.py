import json
import re

def can_handle(query: str) -> bool:
    # Heartbeat agent is not triggered via voice, only via internal timer
    return False

def analyze_transcript(brain, transcript_text: str) -> dict:
    """
    Analysiert das Transkript der letzten Minuten auf Fehler, Perspektiven oder
    erklaerungswuerdige Fachbegriffe.
    Erwartet ein JSON vom LLM zurück.
    """
    if not transcript_text or len(transcript_text.strip()) < 50:
        return None
        
    prompt = [
        {"role": "system", "content": "Du bist ein präziser Hintergrund-Analyst für eine universitäre Vorlesung. WICHTIG: Wenn das Transkript nach einem Alltagsgespräch, Pausen-Gequatsche oder einem Meeting ohne akademischen Inhalt klingt, brich sofort ab (has_finding: false)!\n\nWenn es eine ECHTE Vorlesung ist, suche nach:\n1. Offensichtlichen Fehlern (type: error, color: red)\n2. Wichtigen alternativen Perspektiven (type: perspective, color: yellow)\n3. Einem zentralen Fachbegriff, der im Kontext vorkommt und für Zuhörende wahrscheinlich erklärungsbedürftig ist (type: term, color: green). Wähle nur wirklich relevante Fachbegriffe, nie Alltagswörter, und formuliere eine Definition in höchstens zwei kurzen Sätzen.\n4. Wenn 1. bis 3. nicht zutreffen, aber der Stoff sich gut für eine kurze Verständnisfrage eignet, generiere eine kleine Übungsaufgabe (type: exercise, color: blue).\n\nDu antwortest IMMER in reinem JSON ohne Markdown."},
        {"role": "user", "content": f"Hier ist das Transkript der letzten Minuten:\n\n{transcript_text}\n\nPrüfe dies. Antworte mit genau einem JSON-Objekt:\nFehler/Perspektive: {{\\\"has_finding\\\": true, \\\"type\\\": \\\"error\\\"/\\\"perspective\\\", \\\"bubble_color\\\": \\\"red\\\"/\\\"yellow\\\", \\\"message\\\": \\\"Kurzer Text\\\"}}\nFachbegriff: {{\\\"has_finding\\\": true, \\\"type\\\": \\\"term\\\", \\\"bubble_color\\\": \\\"green\\\", \\\"term\\\": \\\"Begriff\\\", \\\"message\\\": \\\"Kurze Definition\\\"}}\nÜbung: {{\\\"has_finding\\\": true, \\\"type\\\": \\\"exercise\\\", \\\"bubble_color\\\": \\\"blue\\\", \\\"task\\\": \\\"Kurze Frage\\\", \\\"solution\\\": \\\"Kurze Lösung\\\"}}\nNichts/Alltag: {{\\\"has_finding\\\": false}}"}
    ]
    
    try:
        response = brain.ask_llm(prompt)
        
        # Falls das Modell leer antwortet
        if not response or len(response.strip()) == 0:
            return None
            
        # Extrahiere JSON, falls das Modell Text drumherum generiert hat
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            clean_json = json_match.group(0)
        else:
            clean_json = response
            
        result = json.loads(clean_json)
        return result
    except json.JSONDecodeError:
        # Passiert, wenn das Modell sagt "Kein Fehler gefunden" statt JSON
        return None
    except Exception as e:
        print(f"⚠️ Heartbeat-Analyse Fehler: {e}")
        return None

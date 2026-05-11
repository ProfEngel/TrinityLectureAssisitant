import json
import re

def can_handle(query: str) -> bool:
    # Heartbeat agent is not triggered via voice, only via internal timer
    return False

def analyze_transcript(brain, transcript_text: str) -> dict:
    """
    Analysiert das Transkript der letzten Minuten auf Fehler oder alternative Perspektiven.
    Erwartet ein JSON vom LLM zurück.
    """
    if not transcript_text or len(transcript_text.strip()) < 50:
        return None
        
    prompt = [
        {"role": "system", "content": "Du bist ein präziser, leiser Hintergrund-Analyst für eine Vorlesung. Du suchst nach offensichtlichen fachlichen Fehlern des Dozenten oder nach sehr wichtigen alternativen Perspektiven, die fehlen. Du antwortest IMMER in reinem JSON ohne Markdown-Blöcke."},
        {"role": "user", "content": f"Hier ist das Transkript der letzten Minuten:\n\n{transcript_text}\n\nPrüfe dies kurz. Gibt es einen kritischen Fehler oder eine wichtige alternative Perspektive? Antworte in diesem JSON-Format:\n{{\"has_finding\": true/false, \"type\": \"error\"/\"perspective\", \"message\": \"Kurzer, hilfreicher Text\"}}\nWenn alles in Ordnung ist, setze has_finding auf false."}
    ]
    
    try:
        response = brain.ask_llm(prompt)
        # Bereinige Markdown, falls das LLM doch welches schickt
        clean_json = re.sub(r'```json\n?|\n?```', '', response).strip()
        result = json.loads(clean_json)
        return result
    except Exception as e:
        print(f"⚠️ Heartbeat-Analyse fehlgeschlagen: {e}")
        return None

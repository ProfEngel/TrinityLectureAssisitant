import os
import json
import re
import datetime

def can_handle(query: str) -> bool:
    router_text = query.lower()
    triggers = [
        "notiere", "mache eine notiz", "schreibe auf", 
        "füge zur notiz", "erweitere die notiz", 
        "lese die notiz", "zeig mir die notiz", 
        "hake ab", "checkliste", "to-do", "todo", "abgehakt"
    ]
    return any(phrase in router_text for phrase in triggers)

def execute(query: str, context: dict = None) -> dict:
    if not context or "brain" not in context:
        return {"has_payload": False, "html_payload": "", "search_context": ""}
        
    brain = context["brain"]
    notes_dir = os.path.join("memory", "notes")
    os.makedirs(notes_dir, exist_ok=True)
    
    print(f"📝 Notes Agent verarbeitet Anfrage...")
    
    # 1. Ermittle alle existierenden Notizen, um sie dem LLM als Kontext zu geben
    existing_files = []
    if os.path.exists(notes_dir):
        existing_files = [f for f in os.listdir(notes_dir) if f.endswith(".md")]
    
    existing_notes_context = "Verfügbare Notizen im System:\n"
    for file in existing_files:
        topic = file.replace(".md", "")
        filepath = os.path.join(notes_dir, file)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            existing_notes_context += f"\n--- Notiz: {topic} ---\n{content}\n"
        except Exception:
            pass
            
    now = datetime.datetime.now()
    timestamp_str = now.strftime("%d.%m.%Y - %H:%M Uhr")

    prompt = f"""
Du bist ein Notizen- und To-Do-Listen Manager. 
Der User gibt dir einen Sprachbefehl. Deine Aufgabe ist es, den Befehl auszuführen und den vollständigen (neuen oder aktualisierten) Inhalt der Ziel-Notiz zurückzugeben.

{existing_notes_context}

Regeln:
1. Wenn der User eine neue Notiz erstellt, denke dir einen passenden kurzen Namen (topic) aus, verwende keine Leerzeichen (nutze Unterstriche z.B. "ToDo_Heute").
2. Wenn der User eine Checkliste (To-Do Liste) verlangt, formatiere sie mit Markdown-Checkboxes: `- [ ] Aufgabe`.
3. Wenn der User eine Aufgabe als erledigt markiert ("hake ab"), finde die entsprechende Aufgabe in der existierenden Notiz und wechsle `- [ ]` zu `- [x]`.
4. Wenn der User an eine existierende (Nicht-ToDo) Notiz etwas anhängt, füge es am Ende mit einem Zeitstempel hinzu (z.B. `### {timestamp_str}`).
5. Antworte AUSSCHLIESSLICH mit einem validen JSON-Objekt im folgenden Format (ohne Markdown Code-Blöcke oder extra Text drumherum):

{{
  "topic": "Name der Notiz",
  "content": "Der komplette finale Markdown-Inhalt der Notiz",
  "action": "Einer der Werte: CREATED, UPDATED, READ",
  "spoken_confirmation": "Ein kurzer, natürlicher Bestätigungs-Satz für die Sprachausgabe (z.B. 'Ich habe die Aufgabe abgehakt.')"
}}

Sprachbefehl des Users: "{query}"
"""

    response = brain.ask_llm([{"role": "user", "content": prompt}])
    
    # Versuche das JSON zu parsen
    try:
        # Extrahiere JSON, falls das LLM Markdown-Blöcke verwendet hat
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            response_json = json_match.group(0)
        else:
            response_json = response
            
        data = json.loads(response_json)
        topic = data.get("topic", "Neue_Notiz").replace(" ", "_")
        content = data.get("content", "")
        action = data.get("action", "UPDATED")
        spoken_confirmation = data.get("spoken_confirmation", "Die Notiz wurde aktualisiert.")
        
        # Speichere die Datei (außer wenn nur gelesen wird)
        if action in ["CREATED", "UPDATED"] and content:
            filepath = os.path.join(notes_dir, f"{topic}.md")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"✅ Notiz gespeichert unter {filepath}")

        # HTML Payload für visuelles Feedback (Post-it Style)
        import markdown
        # Konvertiere Markdown zu HTML, unterstütze Checkboxes (durch CSS und Ersetzung)
        html_content = markdown.markdown(content)
        # Ersetze Checkboxes für die Anzeige
        html_content = html_content.replace('[ ]', '<input type="checkbox" disabled>')
        html_content = html_content.replace('[x]', '<input type="checkbox" checked disabled>')
        html_content = html_content.replace('[X]', '<input type="checkbox" checked disabled>')
        
        html_payload = f"""
        <!-- KEEP_OPEN -->
        <div style="background-color: #fdfd96; color: #333; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); font-family: 'Comic Sans MS', 'Chalkboard SE', sans-serif; max-width: 600px; margin: 20px auto;">
            <h2 style="margin-top: 0; border-bottom: 1px solid #ccc; padding-bottom: 10px; color: #333;">📝 {topic.replace('_', ' ')}</h2>
            <div style="font-size: 16px; line-height: 1.6;">
                {html_content}
            </div>
        </div>
        """
        
        search_context = f"--- Notizen Agent ---\n{spoken_confirmation}\n"
        
        return {
            "has_payload": True,
            "html_payload": html_payload,
            "search_context": search_context
        }
        
    except json.JSONDecodeError as e:
        print(f"⚠️ JSON-Parsing-Fehler im Notes Agent: {e}\nResponse war: {response}")
        return {
            "has_payload": False,
            "html_payload": "",
            "search_context": "Entschuldigung, beim Verarbeiten der Notiz ist ein Fehler aufgetreten."
        }

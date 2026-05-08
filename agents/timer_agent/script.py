import re
import os

def can_handle(query: str) -> bool:
    """
    Prüft, ob die Anfrage einen Timer-Befehl enthält.
    """
    # Vorverarbeitung wie in brain.py
    query_digits = _convert_number_words(query.lower())
    timer_match = re.search(r'timer.*?(\d+)\s*minute', query_digits)
    if timer_match or ("timer" in query_digits and re.search(r'(\d+)', query_digits)):
        return True
    return False

def execute(query: str, context: dict = None) -> dict:
    """
    Führt die Timer-Logik aus und liefert Payload sowie Suchkontext zurück.
    """
    query_digits = _convert_number_words(query.lower())
    
    # Extraktion der Minuten
    minute_match = re.search(r'(\d+)\s*minute', query_digits)
    if minute_match:
        minutes = int(minute_match.group(1))
    else:
        # Letzte Zahl nehmen
        numbers = re.findall(r'(\d+)', query_digits)
        if numbers:
            minutes = int(numbers[-1])
        else:
            minutes = 1 # Fallback
            
    if minutes > 0:
        html_payload = f"""
        <!-- KEEP_OPEN -->
        <div style="text-align: center; margin-top: 50px;">
            <div style="font-size: 80px; font-weight: bold; text-shadow: 0 0 20px #00bfff; letter-spacing: 5px;" id="timer">{minutes:02d}:00</div>
            <div style="font-size: 14px; opacity: 0.5; margin-top: 10px;">Laufender Timer</div>
        </div>
        <script>
            let time = {minutes * 60};
            let timerEl = document.getElementById('timer');
            let interval = setInterval(() => {{
                time--;
                if(time <= 0) {{
                    clearInterval(interval);
                    timerEl.innerText = "00:00";
                    timerEl.style.color = "#ff4444";
                    timerEl.style.textShadow = "0 0 20px #ff4444";
                    return;
                }}
                let m = Math.floor(time / 60);
                let s = time % 60;
                timerEl.innerText = (m < 10 ? "0"+m : m) + ":" + (s < 10 ? "0"+s : s);
            }}, 1000);
        </script>
        """
        
        search_context = f"--- AGENTIC ACTION ---\nDu hast soeben erfolgreich einen visuellen Countdown-Timer auf {minutes} Minuten im UI eingeblendet. Bestätige dem Nutzer kurz und freundlich, dass der Timer jetzt läuft.\n\n"
        
        return {
            "has_payload": True,
            "html_payload": html_payload,
            "search_context": search_context
        }
        
    return {
        "has_payload": False,
        "html_payload": "",
        "search_context": ""
    }

def _convert_number_words(text: str) -> str:
    """Hilfsfunktion zur Konvertierung von Zahlwörtern in Ziffern."""
    num_map = {
        "ein": 1, "eine": 1, "einen": 1, "eins": 1, "zwei": 2, "zwo": 2, 
        "drei": 3, "vier": 4, "fünf": 5, "sechs": 6, "sieben": 7, 
        "acht": 8, "neun": 9, "zehn": 10, "elf": 11, "zwölf": 12,
        "fünfzehn": 15, "zwanzig": 20, "dreißig": 30, "vierzig": 40,
        "fünfzig": 50, "sechzig": 60, "neunzig": 90
    }
    result = text
    for word, num in num_map.items():
        result = re.sub(rf'\b{word}\b', str(num), result)
    return result

"""
Sandbox Agent — Secure Pyodide Execution Environment
Erkennt Data-Science-, Mathe- und AutoML-Anfragen und generiert
Python-Code, der sicher in der Pyodide-WASM-Sandbox läuft.
"""
import os
import json
import re

# ── Trigger-Keywords ─────────────────────────────────────────────────────────
TRIGGER_KEYWORDS = [
    # Data Science
    "datensatz", "dataset", "csv", "dataframe", "pandas", "analyse",
    "visualisier", "diagramm", "plot", "grafik", "chart", "heatmap",
    "histogramm", "scatter", "boxplot", "seaborn", "matplotlib", "plotly",
    # ML / AutoML
    "trainier", "modell", "klassifizier", "regression", "clustering",
    "scikit", "sklearn", "random forest", "gradient boosting", "svm",
    "machine learning", "automl", "vorhersage", "prediction",
    # Mathematik / Statistik
    "berechn", "integral", "ableitung", "differenzier", "algebra",
    "gleichung", "matrix", "statistik", "varianz", "mittelwert",
    "standardabweichung", "korrelation", "p-wert", "hypothesentest",
    "sympy", "scipy", "numpy", "fourier", "laplace",
    # Explizite Sandbox-Trigger
    "sandbox", "python code", "führe aus", "berechne",
    "zeig mir", "erstelle eine grafik", "zeichne",
]

NEGATIVE_KEYWORDS = [
    "schreibe eine mail", "öffne", "starte", "powerpoint",
    "slide", "folie", "song", "musik",
]


def can_handle(text: str) -> bool:
    """Gibt True zurück, wenn mindestens ein Trigger matcht und kein Negativ-Keyword."""
    t = text.lower()
    if any(neg in t for neg in NEGATIVE_KEYWORDS):
        return False
    return any(kw in t for kw in TRIGGER_KEYWORDS)


def execute(query: str, context: dict) -> dict:
    """
    Hauptmethode des Agents.
    Lässt das LLM Python-Code generieren, verpackt ihn in die sandbox.html
    und gibt den HTML-Payload zurück.
    """
    brain = context.get("brain")
    if not brain:
        return {"has_payload": False, "search_context": ""}

    print("🧮 Sandbox-Agent aktiv: generiere Pyodide-Code…")

    # ── 1. LLM: Python-Code generieren ───────────────────────────────────────
    system_prompt = """Du bist ein spezialisierter Python-Code-Generator für eine sichere WASM-Sandbox (Pyodide).

REGELN:
- Antworte NUR mit reinem Python-Code. KEIN erklärender Text drum herum.
- Kein Markdown-Fencing (keine ```python Blöcke).
- Verfügbare Bibliotheken: numpy, pandas, matplotlib, seaborn, scipy, sympy, scikit-learn, plotly.
- Zum Laden von Online-Datensätzen: import requests (ist via pyodide-http gepatcht und funktioniert).
- Für interaktive Visualisierungen: Plotly BEVORZUGEN (fig.show() wird automatisch abgefangen).
  Matplotlib ist auch möglich (plt.show() wird automatisch abgefangen und als PNG gerendert).
- Für symbolische Mathematik (Ableitungen, Integrale, Gleichungen): sympy verwenden.
- Für AutoML: Trainiere MEHRERE scikit-learn Modelle und vergleiche deren Genauigkeit.
- Ergebnisse per print() ausgeben (werden im Text-Output-Bereich angezeigt).
- Code muss vollständig und direkt ausführbar sein — keine Platzhalter, keine TODOs.
- Wähle ansprechende Plotly/Seaborn Themes (dark_minimal, plotly_dark etc.).
- ACHTE UNBEDINGT auf fehlerfreie Python-Syntax! Jede Zeile muss valider Python-Code sein. Vermeide jegliche Tippfehler und halbe oder fehlerhafte Sätze bei Importen (wie z. B. 'from sklearn.compose | pipeline').
- SPEZIALFALL Philadelphia Crime: Nutze die Tabelle 'incidents_part1_part2'. Die Geokoordinaten dort heißen 'point_x' (Longitude) und 'point_y' (Latitude), NICHT 'lat'/'lng'! Die SQL-Query lautet: https://phl.carto.com/api/v2/sql?q=SELECT+*+FROM+incidents_part1_part2+WHERE+point_x+IS+NOT+NULL+AND+point_y+IS+NOT+NULL+LIMIT+2000&format=csv. Achte darauf, in Plotly/Modellen lat="point_y" und lon="point_x" zu setzen!

BEISPIEL-MUSTER für Datensatz-Download:
  import requests
  import pandas as pd
  import io
  url = "https://raw.githubusercontent.com/.../dataset.csv"
  response = requests.get(url)
  df = pd.read_csv(io.StringIO(response.text))
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": query},
    ]

    python_code = brain.ask_llm(messages)

    # Sicherheits-Bereinigung: Markdown-Fences entfernen, falls das LLM sie trotzdem schreibt
    python_code = re.sub(r"^```(?:python)?\s*", "", python_code.strip(), flags=re.IGNORECASE)
    python_code = re.sub(r"\s*```$", "", python_code.strip())
    python_code = python_code.strip()

    if not python_code:
        return {
            "has_payload": False,
            "search_context": "Der Sandbox-Agent konnte keinen Code generieren.",
        }

    print(f"📝 Generierter Code ({len(python_code)} Zeichen)")

    # ── 2. sandbox.html laden und Code einfügen ───────────────────────────────
    sandbox_html_path = os.path.join(os.path.dirname(__file__), "sandbox.html")
    try:
        with open(sandbox_html_path, "r", encoding="utf-8") as f:
            sandbox_html = f.read()
    except FileNotFoundError:
        return {"has_payload": False, "search_context": "sandbox.html nicht gefunden."}

    # Code als JS-String escapen und per window.injectCode() einschleusen
    escaped_code = python_code.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
    inject_script = f"""
<script>
// Auto-Inject durch Trinity Sandbox-Agent
window.addEventListener('load', function() {{
    // Warte bis Pyodide bereit ist
    var attempts = 0;
    function tryInject() {{
        if (window.injectCode) {{
            window.injectCode(`{escaped_code}`);
        }} else if (attempts < 60) {{
            attempts++;
            setTimeout(tryInject, 500);
        }}
    }}
    setTimeout(tryInject, 800);
}});
</script>
"""
    # Script vor </body> einfügen
    sandbox_with_code = sandbox_html.replace("</body>", inject_script + "\n</body>")

    # Volle Seite als Payload (KEEP_OPEN damit das Fenster offen bleibt)
    full_html = "<!-- KEEP_OPEN -->\n<!-- FULLPAGE -->\n" + sandbox_with_code

    return {
        "has_payload": True,
        "html_payload": full_html,
        "search_context": (
            f"--- SANDBOX-AGENT ---\n"
            f"Ich habe Python-Code für die Pyodide-Sandbox generiert und ausgeführt.\n"
            f"Anfrage: {query}\n\n"
            f"Generierter Code:\n```python\n{python_code}\n```\n"
        ),
    }

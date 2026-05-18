---
name: Secure Sandbox Agent
description: "Führt von der KI generierten Python-Code für Data-Science, Mathematik und AutoML 100% isoliert im Browser aus."
---

# Secure Sandbox Agent (Pyodide)

Dieser Agent ist dafür zuständig, mathematische, statistische oder datengetriebene Anfragen in ausführbaren Python-Code zu übersetzen. Der generierte Code wird NICHT auf dem lokalen Dateisystem des Rechners ausgeführt, sondern an die Pyodide-WASM-Sandbox in Trinitys Benutzeroberfläche gesendet.

## Workflow

1.  Der Nutzer stellt eine Anfrage (z.B. "Lade den Titanic Datensatz und zeige die Korrelationsmatrix als Heatmap").
2.  Trinity identifiziert die Aufgabe als datengetrieben.
3.  Trinity nutzt den `sandbox_agent`, um reinen Python-Code zu generieren.
    *   **WICHTIG:** Der Code muss für die Pyodide-Umgebung geschrieben sein.
    *   **WICHTIG:** Plotly, Seaborn, Matplotlib, Scikit-Learn und Numpy sind verfügbar.
    *   Wenn Daten geladen werden, MUSS `pyodide.http.pyfetch` verwendet werden, anstelle von `requests`!
4.  Der Code wird in einem JSON-Payload verpackt und an die `trinity_app.py` übergeben.
5.  Die UI lädt `sandbox.html` und injiziert das Python-Skript in die WASM-Laufzeitumgebung.

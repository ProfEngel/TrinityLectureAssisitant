import re
import requests

def can_handle(query: str) -> bool:
    router_text = query.lower()
    return any(word in router_text for word in ["aktienkurs", "aktie", "kurs von", "preis von", "stock", "krypto", "bitcoin", "ethereum"])

def execute(query: str, context: dict = None) -> dict:
    lower_query = query.lower()
    
    # Ticker-Symbol extrahieren
    ticker_match = re.search(r'\b([A-Z]{2,5})\b', query)
    
    # Versuche auch geschriebene Namen zu erkennen
    known_tickers = {
        "apple": "AAPL", "microsoft": "MSFT", "google": "GOOGL", "alphabet": "GOOGL",
        "amazon": "AMZN", "tesla": "TSLA", "nvidia": "NVDA", "meta": "META",
        "netflix": "NFLX", "sap": "SAP", "siemens": "SIE.DE", "volkswagen": "VOW3.DE",
        "bmw": "BMW.DE", "bayer": "BAYN.DE", "bitcoin": "BTC-USD", "ethereum": "ETH-USD"
    }
    ticker = None
    for name, sym in known_tickers.items():
        if name in lower_query:
            ticker = sym
            break
    if not ticker and ticker_match:
        ticker = ticker_match.group(1)

    if ticker:
        try:
            quote_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=5d"
            resp = requests.get(quote_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                meta = data["chart"]["result"][0]["meta"]
                price = meta.get("regularMarketPrice", 0)
                prev_close = meta.get("chartPreviousClose", meta.get("previousClose", price))
                currency = meta.get("currency", "")
                change = price - prev_close
                change_pct = (change / prev_close * 100) if prev_close else 0
                color = "#00ff88" if change >= 0 else "#ff4444"
                arrow = "▲" if change >= 0 else "▼"
                name_display = meta.get("shortName", ticker)

                # Historische Punkte für Mini-Chart
                closes = data["chart"]["result"][0]["indicators"]["quote"][0].get("close", [])
                closes = [c for c in closes if c is not None][-5:]
                min_p = min(closes) if closes else price
                max_p = max(closes) if closes else price
                points_count = len(closes)
                svg_width = 280
                svg_height = 60
                if points_count > 1 and max_p != min_p:
                    pts = " ".join([
                        f"{int(i * svg_width / (points_count-1))},{int(svg_height - (c - min_p) / (max_p - min_p) * svg_height)}"
                        for i, c in enumerate(closes)
                    ])
                    sparkline = f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"/>'
                else:
                    sparkline = f'<line x1="0" y1="30" x2="{svg_width}" y2="30" stroke="{color}" stroke-width="2"/>'

                html_payload = f"""
<!-- KEEP_OPEN -->
<h2 style='margin-top:0;font-weight:300;border-bottom:1px solid rgba(255,255,255,0.2);padding-bottom:10px;font-size:18px;'>📈 {name_display}</h2>
<div style='text-align:center;padding:15px 0;'>
  <div style='font-size:48px;font-weight:bold;color:{color};text-shadow:0 0 20px {color};'>{price:.2f} <span style='font-size:20px;'>{currency}</span></div>
  <div style='font-size:18px;color:{color};margin-top:5px;'>{arrow} {change:+.2f} ({change_pct:+.2f}%)</div>
  <div style='font-size:12px;opacity:0.5;margin-top:5px;'>Vortag: {prev_close:.2f} {currency}</div>
</div>
<svg width='{svg_width}' height='{svg_height}' style='display:block;margin:0 auto;opacity:0.8;'>{sparkline}</svg>
<div style='font-size:11px;opacity:0.4;text-align:center;margin-top:8px;'>5-Tage Verlauf · Yahoo Finance</div>"""
                
                search_context = (
                    f"--- AGENTIC ACTION: ABGESCHLOSSEN ---\n"
                    f"Du hast den Kurs von {name_display} ({ticker}) live abgerufen: "
                    f"{price:.2f} {currency} ({arrow} {change_pct:+.2f}% heute). "
                    f"Das interaktive Chart ist BEREITS im Nebenfenster sichtbar.\n"
                    f"DEINE AUFGABE JETZT: Sag NUR einen einzigen kurzen Satz auf Deutsch, der den Kurs bestätigt. "
                    f"Beispiel: 'Nvidia steht gerade bei 950 Dollar, heute plus zwei Prozent.'\n"
                    f"VERBOTEN: CSV, Tabellen, Listen, Markdown, erklärende Sätze, Quellenangaben.\n\n"
                )
                
                return {
                    "has_payload": True,
                    "html_payload": html_payload,
                    "search_context": search_context
                }
        except Exception as e:
            print(f"⚠️ Aktienkurs Fehler: {e}")
            
    return {"has_payload": False, "html_payload": "", "search_context": ""}

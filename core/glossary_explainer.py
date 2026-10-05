"""Short, optional lecture glossary using Trinity's already configured LLM."""

from __future__ import annotations

import json
import re

import requests


def explain_lecture_term(text: str, config: dict) -> dict:
    source = str(text or "").strip()[:1200]
    if len(source) < 12:
        return {"ok": True, "term": "", "definition": ""}
    llm = config.get("llm", {})
    slot = llm.get(str(llm.get("active_slot") or "local"), {})
    url = str(slot.get("url") or "").strip()
    model = str(slot.get("model") or "").strip()
    if not url or not model:
        return {"ok": True, "term": "", "definition": ""}
    prompt = (
        "Prüfe den folgenden gerade gehörten deutschen Satz. Wähle höchstens EIN "
        "ungewöhnliches Fach- oder Fremdwort, das Studierende kurz erklärt brauchen. "
        "Nur wenn ein solches Wort wirklich wörtlich im Satz steht, antworte mit "
        "JSON {\"term\":\"Wort\",\"definition\":\"maximal 12 einfache Wörter\"}. "
        "Sonst antworte mit {\"term\":\"\",\"definition\":\"\"}. Keine weiteren Zeichen.\n\n"
        + source
    )
    headers = {"Content-Type": "application/json"}
    if slot.get("api_key"):
        headers["Authorization"] = f"Bearer {slot['api_key']}"
    response = requests.post(
        url,
        headers=headers,
        json={"model": model, "messages": [{"role": "user", "content": prompt}],
              "temperature": 0, "max_tokens": 120},
        timeout=8,
    )
    response.raise_for_status()
    content = str(response.json()["choices"][0]["message"].get("content") or "")
    match = re.search(r"\{[^{}]*\}", content, re.S)
    if not match:
        return {"ok": True, "term": "", "definition": ""}
    data = json.loads(match.group())
    term = str(data.get("term") or "").strip()[:40]
    definition = str(data.get("definition") or "").strip()[:120]
    if not term or not definition or term.casefold() not in source.casefold():
        return {"ok": True, "term": "", "definition": ""}
    return {"ok": True, "term": term, "definition": definition}

"""Shared Agentenbuilder skill for Trinity's controlled agent forge."""

import html
import re


PRIORITY = 99

TRIGGER_PATTERNS = (
    r"\bagentenbuilder\b",
    r"\bagent builder\b",
    r"\b(?:baue|erstelle|entwickle)\s+(?:einen\s+)?agenten\b",
    r"\bneuen\s+agenten\b",
)


def can_handle(query: str) -> bool:
    text = str(query or "").casefold()
    return any(re.search(pattern, text) for pattern in TRIGGER_PATTERNS)


def execute(query: str, context=None) -> dict:
    context = context or {}
    decision = context.get("task_decision")
    job = getattr(decision, "job", None) if decision is not None else None
    job_id = (job or {}).get("job_id", "")
    route = getattr(decision, "route", "agent_forge") if decision is not None else "agent_forge"
    title = _short_title(query)

    message = (
        "Ich habe den Agentenbuilder aktiviert. "
        "Der naechste sichere Schritt ist: Anforderungen klaeren, Plan erstellen, "
        "Staging-Agent bauen, Tests/Quality-Gates laufen lassen und erst nach Deiner "
        "Freigabe produktiv registrieren."
    )
    if job_id:
        message += f" Der Builder-Auftrag laeuft unter Job {job_id}."

    html_payload = _html_payload(title=title, query=query, job_id=job_id, route=route)
    return {
        "direct_answer": message,
        "has_payload": True,
        "html_payload": html_payload,
        "search_context": "",
    }


def _short_title(query: str) -> str:
    compact = " ".join(str(query or "").split())
    if not compact:
        return "Neuer Trinity-Agent"
    return compact[:90]


def _html_payload(title: str, query: str, job_id: str, route: str) -> str:
    rows = [
        ("1", "Anforderung erfassen", "Was soll der Agent koennen, welche Trigger, welche Grenzen?"),
        ("2", "Plan erstellen", "Harness, Rechte, Pfade, Tests und Quality-Gates festlegen."),
        ("3", "Staging bauen", "Code, Manifest, Beispiele und lokale Tests in skills/staging ablegen."),
        ("4", "Validieren", "Tests ausfuehren, Ergebnis pruefen, Rechte- und Freigabecheck."),
        ("5", "Freigabe & Release", "Nach Deiner Freigabe nach personal/shared promoten und katalogisieren."),
    ]
    items = "".join(
        "<li><strong>{step}. {name}</strong><br><span>{desc}</span></li>".format(
            step=html.escape(step),
            name=html.escape(name),
            desc=html.escape(desc),
        )
        for step, name, desc in rows
    )
    job_line = (
        f"<p><strong>Job:</strong> {html.escape(job_id)} · Route: {html.escape(route)}</p>"
        if job_id
        else "<p><strong>Job:</strong> noch kein persistenter Job uebergeben.</p>"
    )
    return (
        "<section style='font-family: system-ui; padding: 20px; color: #e8f3ff; "
        "background: linear-gradient(135deg,#111827,#172554); border-radius: 16px;'>"
        "<h2 style='margin-top:0;'>Trinity Agentenbuilder</h2>"
        f"<p><strong>Auftrag:</strong> {html.escape(title)}</p>"
        f"{job_line}"
        "<ol style='line-height:1.45;'>"
        f"{items}"
        "</ol>"
        "<p style='color:#bfdbfe;'>Der Builder ist absichtlich freigabeorientiert: "
        "Produktive Aktivierung passiert erst nach Tests und Deiner Entscheidung.</p>"
        f"<details><summary>Originalauftrag</summary><pre style='white-space:pre-wrap'>{html.escape(str(query or ''))}</pre></details>"
        "</section>"
    )

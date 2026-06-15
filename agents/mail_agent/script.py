import json
import re
import subprocess


REQUIRED_CAPABILITIES = {"mail_automation"}


TRIGGERS = [
    "mail",
    "mails",
    "email",
    "e-mail",
    "postfach",
    "eingang",
    "inbox",
    "ungelesene",
]


def can_handle(query: str) -> bool:
    router_text = query.lower()
    if any(trigger in router_text for trigger in TRIGGERS):
        return True

    draft_phrases = [
        "schreibe an",
        "antwort an",
        "mail an",
        "email an",
        "e-mail an",
    ]
    return any(phrase in router_text for phrase in draft_phrases)


def execute(query: str, context: dict = None) -> dict:
    router_text = query.lower()

    if _is_open_mail_command(router_text):
        return _open_mail()

    if _is_unread_command(router_text):
        return _show_unread_messages()

    if _is_search_command(router_text):
        return _search_messages(query, context)

    if _is_draft_command(router_text):
        return _create_draft(query, context)

    return _open_mail()


def _is_open_mail_command(router_text: str) -> bool:
    return (
        ("öffne" in router_text or "starte" in router_text or "zeige" in router_text)
        and any(word in router_text for word in ["mail", "mails", "email", "e-mail", "postfach", "eingang", "inbox"])
    )


def _is_unread_command(router_text: str) -> bool:
    return any(phrase in router_text for phrase in [
        "ungelesene mails",
        "ungelesene mail",
        "ungelesenen mails",
        "neue mails",
        "neue mail",
        "was ist im posteingang",
        "was liegt im posteingang",
        "check meine mails",
        "prüfe meine mails",
        "mail eingang",
        "maileingang",
        "inbox",
    ])


def _is_search_command(router_text: str) -> bool:
    return any(phrase in router_text for phrase in [
        "suche mail",
        "such mail",
        "finde mail",
        "such in mail",
        "suche in mail",
        "suche in mails",
        "finde in mails",
    ])


def _is_draft_command(router_text: str) -> bool:
    return any(phrase in router_text for phrase in [
        "schreibe eine mail",
        "schreib eine mail",
        "erstelle eine mail",
        "mail an",
        "email an",
        "e-mail an",
        "antwort an",
        "antworte an",
    ])


def _open_mail() -> dict:
    script = '''
    tell application "Mail"
        activate
    end tell
    '''
    ok, error = _run_osascript(script)
    if not ok:
        return _error_result("Mail konnte nicht geöffnet werden.", error)

    return {
        "has_payload": False,
        "html_payload": "",
        "search_context": "--- Mail Agent ---\nMail wurde geöffnet.\n",
    }


def _show_unread_messages(limit: int = 8) -> dict:
    script = f'''
    tell application "Mail"
        activate
        set outputLines to {{}}
        set unreadMessages to (messages of inbox whose read status is false)
        set messageCount to count of unreadMessages
        set maxItems to {limit}
        if messageCount < maxItems then set maxItems to messageCount
        repeat with i from 1 to maxItems
            set m to item i of unreadMessages
            set senderText to sender of m
            set subjectText to subject of m
            set dateText to date received of m as string
            set end of outputLines to senderText & "||" & subjectText & "||" & dateText
        end repeat
        set AppleScript's text item delimiters to linefeed
        return (messageCount as string) & linefeed & (outputLines as text)
    end tell
    '''
    ok, output = _run_osascript(script)
    if not ok:
        return _error_result("Ich konnte die ungelesenen Mails nicht auslesen.", output)

    lines = [line for line in output.splitlines() if line.strip()]
    total = _safe_int(lines[0]) if lines else 0
    messages = []
    for line in lines[1:]:
        parts = line.split("||")
        if len(parts) >= 3:
            messages.append({"sender": parts[0], "subject": parts[1], "date": parts[2]})

    html_items = "".join(
        f"<li style='margin-bottom:10px;'><b>{_html_escape(item['subject'])}</b><br>"
        f"<span style='opacity:.85'>{_html_escape(item['sender'])}</span><br>"
        f"<span style='font-size:13px; opacity:.7'>{_html_escape(item['date'])}</span></li>"
        for item in messages
    )
    if not html_items:
        html_items = "<li>Keine ungelesenen Mails gefunden.</li>"

    html_payload = f"""
    <!-- KEEP_OPEN -->
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; max-width:720px; margin:20px auto; line-height:1.45;">
        <h2 style="margin:0 0 12px; font-size:20px;">Mail Eingang</h2>
        <p style="margin:0 0 14px; opacity:.85;">{total} ungelesene Mail(s), hier die neuesten {len(messages)}.</p>
        <ul style="padding-left:20px; margin:0;">{html_items}</ul>
    </div>
    """

    summary = f"Du hast {total} ungelesene Mail(s)."
    if messages:
        summary += " Neueste Betreffzeilen: " + "; ".join(item["subject"] for item in messages[:3])

    return {
        "has_payload": True,
        "html_payload": html_payload,
        "search_context": f"--- Mail Agent ---\n{summary}\n",
    }


def _search_messages(query: str, context: dict = None) -> dict:
    search_term = _extract_search_term(query, context)
    if not search_term:
        return {
            "has_payload": False,
            "html_payload": "",
            "search_context": "--- Mail Agent ---\nBitte nenne noch, wonach ich in Mail suchen soll.\n",
        }

    script = f'''
    tell application "Mail"
        activate
        set outputLines to {{}}
        set matches to (messages of inbox whose subject contains "{_as_applescript_string(search_term)}" or sender contains "{_as_applescript_string(search_term)}")
        set messageCount to count of matches
        set maxItems to 8
        if messageCount < maxItems then set maxItems to messageCount
        repeat with i from 1 to maxItems
            set m to item i of matches
            set senderText to sender of m
            set subjectText to subject of m
            set dateText to date received of m as string
            set end of outputLines to senderText & "||" & subjectText & "||" & dateText
        end repeat
        set AppleScript's text item delimiters to linefeed
        return (messageCount as string) & linefeed & (outputLines as text)
    end tell
    '''
    ok, output = _run_osascript(script)
    if not ok:
        return _error_result("Die Mail-Suche ist fehlgeschlagen.", output)

    lines = [line for line in output.splitlines() if line.strip()]
    total = _safe_int(lines[0]) if lines else 0
    messages = []
    for line in lines[1:]:
        parts = line.split("||")
        if len(parts) >= 3:
            messages.append({"sender": parts[0], "subject": parts[1], "date": parts[2]})

    html_items = "".join(
        f"<li style='margin-bottom:10px;'><b>{_html_escape(item['subject'])}</b><br>"
        f"<span style='opacity:.85'>{_html_escape(item['sender'])}</span><br>"
        f"<span style='font-size:13px; opacity:.7'>{_html_escape(item['date'])}</span></li>"
        for item in messages
    )
    if not html_items:
        html_items = "<li>Keine Treffer gefunden.</li>"

    html_payload = f"""
    <!-- KEEP_OPEN -->
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; max-width:720px; margin:20px auto; line-height:1.45;">
        <h2 style="margin:0 0 12px; font-size:20px;">Mail Suche: {_html_escape(search_term)}</h2>
        <p style="margin:0 0 14px; opacity:.85;">{total} Treffer im Posteingang.</p>
        <ul style="padding-left:20px; margin:0;">{html_items}</ul>
    </div>
    """

    return {
        "has_payload": True,
        "html_payload": html_payload,
        "search_context": f"--- Mail Agent ---\nIch habe {total} Mail-Treffer zu '{search_term}' gefunden.\n",
    }


def _create_draft(query: str, context: dict = None) -> dict:
    draft = _extract_draft(query, context)
    if not draft.get("body"):
        return {
            "has_payload": False,
            "html_payload": "",
            "search_context": "--- Mail Agent ---\nIch brauche noch Inhalt für den Mail-Entwurf.\n",
        }

    recipient = draft.get("recipient", "").strip()
    subject = draft.get("subject", "").strip() or "Kurze Nachricht"
    body = draft.get("body", "").strip()

    script = f'''
    tell application "Mail"
        activate
        set newMessage to make new outgoing message with properties {{subject:"{_as_applescript_string(subject)}", content:"{_as_applescript_string(body)}" & return & return, visible:true}}
        tell newMessage
            if "{_as_applescript_string(recipient)}" is not "" then
                make new to recipient at end of to recipients with properties {{address:"{_as_applescript_string(recipient)}"}}
            end if
        end tell
    end tell
    '''
    ok, error = _run_osascript(script)
    if not ok:
        return _error_result("Der Mail-Entwurf konnte nicht erstellt werden.", error)

    html_payload = f"""
    <!-- KEEP_OPEN -->
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; max-width:720px; margin:20px auto; line-height:1.45;">
        <h2 style="margin:0 0 12px; font-size:20px;">Mail Entwurf</h2>
        <p style="margin:0 0 8px;"><b>An:</b> {_html_escape(recipient or 'Bitte in Mail ergänzen')}</p>
        <p style="margin:0 0 14px;"><b>Betreff:</b> {_html_escape(subject)}</p>
        <div style="white-space:pre-wrap; padding:14px; border:1px solid rgba(255,255,255,.2); border-radius:8px;">{_html_escape(body)}</div>
    </div>
    """

    return {
        "has_payload": True,
        "html_payload": html_payload,
        "search_context": "--- Mail Agent ---\nIch habe einen Mail-Entwurf in Apple Mail geöffnet. Er wurde nicht gesendet.\n",
    }


def _extract_search_term(query: str, context: dict = None) -> str:
    brain = (context or {}).get("brain")
    if brain:
        response = brain.ask_llm([{"role": "user", "content": (
            "Extrahiere aus diesem Sprachbefehl den Suchbegriff für Apple Mail. "
            "Antworte nur mit dem Suchbegriff, ohne Erklärung.\n"
            f"Sprachbefehl: {query}"
        )}])
        term = response.strip().strip('"')
        if term:
            return term[:120]

    cleaned = re.sub(r"(?i)(trinity|suche|such|finde|mail|mails|email|e-mail|in|nach)", " ", query)
    return " ".join(cleaned.split())[:120]


def _extract_draft(query: str, context: dict = None) -> dict:
    brain = (context or {}).get("brain")
    if not brain:
        return {"recipient": "", "subject": "Kurze Nachricht", "body": query}

    response = brain.ask_llm([{"role": "user", "content": f"""
Du bist ein Assistent für sichere Mail-Entwürfe. Extrahiere aus dem Sprachbefehl Empfänger, Betreff und Nachrichtentext.

Regeln:
1. Sende niemals eine Mail. Erstelle nur einen Entwurf.
2. Wenn keine echte E-Mail-Adresse genannt wird, lasse "recipient" leer und nutze Namen nicht als Adresse.
3. Formuliere den Nachrichtentext freundlich, knapp und natürlich auf Deutsch.
4. Antworte ausschließlich als valides JSON:

{{
  "recipient": "email@example.com oder leer",
  "subject": "kurzer Betreff",
  "body": "finaler Mailtext"
}}

Sprachbefehl: "{query}"
"""}])

    try:
        match = re.search(r"\{.*\}", response, re.DOTALL)
        payload = match.group(0) if match else response
        data = json.loads(payload)
    except Exception:
        data = {"recipient": "", "subject": "Kurze Nachricht", "body": query}

    recipient = data.get("recipient", "")
    if recipient and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", recipient):
        recipient = ""

    return {
        "recipient": recipient,
        "subject": data.get("subject", "Kurze Nachricht"),
        "body": data.get("body", query),
    }


def _run_osascript(script: str):
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )
    except Exception as exc:
        return False, str(exc)

    if result.returncode != 0:
        return False, (result.stderr or result.stdout).strip()
    return True, result.stdout.strip()


def _as_applescript_string(value: str) -> str:
    return (value or "").replace("\\", "\\\\").replace('"', '\\"')


def _html_escape(value: str) -> str:
    return (
        (value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _safe_int(value: str) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _error_result(message: str, details: str) -> dict:
    print(f"⚠️ Mail Agent: {message} {details}")
    return {
        "has_payload": False,
        "html_payload": "",
        "search_context": f"--- Mail Agent ---\n{message} macOS meldet: {details}\n",
    }

"""Explicit desktop app launch intents; never arbitrary shell commands."""
import re
import unicodedata

APPLICATIONS = {
    "mail": ("Mail", "com.apple.mail"),
    "excel": ("Excel", "com.microsoft.Excel"),
    "word": ("Word", "com.microsoft.Word"),
    "powerpoint": ("PowerPoint", "com.microsoft.Powerpoint"),
    "chrome": ("Chrome", "com.google.Chrome"),
    "chatgpt": ("ChatGPT", "com.openai.chat"),
    "finder": ("Finder", "com.apple.finder"),
    "textedit": ("TextEdit", "com.apple.TextEdit"),
    "safari": ("Safari", "com.apple.Safari"),
    "outlook": ("Outlook", "com.microsoft.Outlook"),
}


def app_to_open(text):
    plain = unicodedata.normalize("NFKD", str(text).casefold())
    plain = "".join(c for c in plain if not unicodedata.combining(c))
    plain = re.sub(r"[^a-z0-9]+", " ", plain).strip()
    match = re.fullmatch(r"trinity (?:bitte )?(?:offne|starte) (?:die app |das programm )?(.+?)(?: bitte)?", plain)
    if not match:
        return None
    name = match.group(1).replace(" ", "")
    if name == "googlechrome":
        name = "chrome"
    return APPLICATIONS.get(name)


def mail_navigation(text):
    plain = unicodedata.normalize("NFKD", str(text).casefold())
    plain = "".join(c for c in plain if not unicodedata.combining(c))
    plain = re.sub(r"[^a-z0-9]+", " ", plain).strip()
    return {
        "trinity nachste mail": (125, False, "Nächste Mail."),
        "trinity vorherige mail": (126, False, "Vorherige Mail."),
        "trinity beantworte diese mail": (15, True, "Antwortentwurf geöffnet."),
        "trinity antworte auf diese mail": (15, True, "Antwortentwurf geöffnet."),
        "trinity neue mail": (45, True, "Neuer Mailentwurf geöffnet."),
        "trinity suche in mail": (3, True, "Mail-Suche geöffnet."),
    }.get(plain)

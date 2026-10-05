"""Explicit voice requests for a CURRENT desktop window, not continuous video."""
import hashlib
import re
import unicodedata


def normalized(text):
    text = unicodedata.normalize("NFKD", str(text).lower())
    return " ".join(re.sub(r"[^a-z0-9]+", " ", "".join(c for c in text if not unicodedata.combining(c))).split())


def wants_window(text):
    text = normalized(text)
    return bool(re.search(
        r"\b(?:was siehst|siehst du|schau (?:mal |bitte )?(?:hier|auf|in)|"
        r"(?:aktive[nms]?|offene[nms]?|freigegebene[nms]?) (?:fenster|programm|app)|"
        r"(?:dieses|diesem|dieser) (?:fenster|bildschirm|programm)|"
        r"(?:diese|dieser) (?:tabelle|folie|prasentation)|"
        r"hier (?:im|in|auf)|auf meinem (?:bildschirm|desktop))\b", text))


def fingerprint(text):
    return hashlib.sha256(normalized(text).encode()).hexdigest()

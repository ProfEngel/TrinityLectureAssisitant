"""German-only input and output policy for the Eve runtime."""

from __future__ import annotations

import re


GERMAN_ONLY_PROMPT = (
    "Sprich ausschließlich Deutsch. Eigennamen, Produktnamen, Modellnamen und "
    "technische Fachbegriffe dürfen unverändert bleiben. Gib nie internes Thinking "
    "oder Reasoning aus. Antworte bei Sprachdialogen zunächst knapp und natürlich."
)

_GERMAN_MARKERS = {
    "aber", "auch", "bitte", "das", "der", "die", "ein", "eine", "für", "ich",
    "ist", "kann", "mit", "nicht", "oder", "sind", "und", "was", "wie", "wir",
}
_ENGLISH_MARKERS = {
    "and", "are", "can", "could", "how", "is", "please", "should", "the", "this",
    "what", "with", "would", "you",
}


def looks_clearly_non_german(text: str, minimum_words: int = 8) -> bool:
    words = re.findall(r"[a-zA-ZäöüÄÖÜß]+", str(text or "").casefold())
    if len(words) < minimum_words:
        return False
    german = sum(word in _GERMAN_MARKERS for word in words)
    english = sum(word in _ENGLISH_MARKERS for word in words)
    return english >= 3 and english >= german * 2 + 1


def enforce_input_language(text: str) -> str | None:
    if looks_clearly_non_german(text):
        return "Bitte sprich Deutsch mit mir. Namen und technische Begriffe dürfen natürlich englisch bleiben."
    return None


def clean_speakable_text(text: str) -> str:
    value = re.sub(r"```.*?```", "", str(text or ""), flags=re.DOTALL)
    value = re.sub(r"[`*_#>|]", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def segment_for_speech(text: str, max_chars: int = 280) -> list[str]:
    cleaned = clean_speakable_text(text)
    if not cleaned:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip()
        if current and len(candidate) > max_chars:
            chunks.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks

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
    # A word-count heuristic cannot distinguish English technical vocabulary
    # or multilingual STT errors from an intentionally English utterance.
    # Accept all input; the system prompt still prefers German answers.
    return None


def clean_speakable_text(text: str) -> str:
    value = re.sub(r"```.*?```", "", str(text or ""), flags=re.DOTALL)
    value = re.sub(r"^\s*\[SPEAKER\]\s*", "", value, flags=re.IGNORECASE)
    value = re.sub(r"[`*_#>|]", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def segment_for_speech(text: str, max_chars: int = 280) -> list[str]:
    cleaned = clean_speakable_text(text)
    if not cleaned:
        return []
    sentences = []
    for sentence in re.split(r"(?<=[.!?])\s+", cleaned):
        # Dictated prose and model output sometimes contain no punctuation.
        # Bound those chunks too, without cutting a word in half.
        piece_limit = min(max_chars, 120) if not sentences else max_chars
        while len(sentence) > piece_limit:
            split_at = sentence.rfind(" ", 0, piece_limit + 1)
            if split_at <= 0:
                split_at = piece_limit
            sentences.append(sentence[:split_at])
            sentence = sentence[split_at:].strip()
            piece_limit = max_chars
        if sentence:
            sentences.append(sentence)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip()
        chunk_limit = min(max_chars, 120) if not chunks else max_chars
        if current and len(candidate) > chunk_limit:
            chunks.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks

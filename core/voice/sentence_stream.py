"""Incremental, visible-only OpenAI SSE speech; no reasoning fallback."""
import json
import re


from core.voice.cancellation import StreamCancelled


def stream_sentences(response, emit, cancelled=lambda: False):
    # SSE is always UTF-8. requests otherwise assumes ISO-8859-1 for a
    # text/event-stream response without charset, corrupting umlauts before TTS.
    # Its incremental decoder also handles multibyte characters split over chunks.
    response.encoding = "utf-8"
    pending = ""
    visible = []
    thinking = False
    fenced = False
    first = True
    completed = False
    for line in response.iter_lines(chunk_size=1, decode_unicode=True):
        if cancelled():
            raise StreamCancelled()
        if not line or not line.startswith("data:"):
            continue
        raw = line[5:].strip()
        if raw == "[DONE]":
            completed = True
            break
        event = json.loads(raw)
        if event.get("error"):
            raise ValueError("Model streaming error")
        choices = event.get("choices") or []
        if not choices:
            continue
        choice = choices[0]
        pending += choice.get("delta", {}).get("content") or ""
        if len(pending) > 65536:
            raise ValueError("Oversized hidden or unpunctuated model output")
        completed = completed or bool(choice.get("finish_reason"))
        # Hold partial tags/fences until complete; never speak hidden blocks.
        while pending:
            if thinking:
                end = pending.lower().find("</think>")
                if end < 0:
                    break
                pending = pending[end + 8:]
                thinking = False
                continue
            if fenced:
                end = pending.find("```")
                if end < 0:
                    break
                pending = pending[end + 3:]
                fenced = False
                continue
            pending = pending.lstrip()
            if pending.lower().startswith("<think>"):
                thinking, pending = True, pending[7:]
                continue
            if pending.startswith("```"):
                fenced, pending = True, pending[3:]
                continue
            boundary = None
            for candidate in re.finditer(r'[.!?](?:["”»])?(?:\s|$)', pending):
                prefix = pending[:candidate.end()].strip()
                if (re.search(r'\b(?:Dr|Prof|bzw|ca|z|B)\.$', prefix)
                        or re.search(r'\d\.$', prefix)):
                    continue
                boundary = candidate
                break
            if not boundary or boundary.end() == len(pending):
                break  # wait for following token: decimals/abbreviations may continue
            sentence, pending = pending[:boundary.end()].strip(), pending[boundary.end():]
            if '<' in sentence or '```' in sentence:
                raise ValueError("Unexpected hidden markup in visible sentence")
            if first and any(x in sentence.casefold() for x in (
                "thinking process", "reasoning process", "self-correction", "analyze user input")):
                raise ValueError("Unsafe visible reasoning in model output")
            first = False
            from .language_policy import clean_speakable_text
            sentence = clean_speakable_text(sentence)
            if sentence:
                emit(sentence)
                visible.append(sentence)
    if cancelled():
        raise StreamCancelled()
    if not completed:
        raise ValueError("Incomplete model stream")
    if pending.strip() and not thinking and not fenced:
        from .language_policy import clean_speakable_text
        if '<' in pending or '```' in pending or any(x in pending.casefold() for x in (
            "thinking process", "reasoning process", "self-correction", "analyze user input")):
            raise ValueError("Unsafe trailing model content")
        tail = clean_speakable_text(pending)
        if tail:
            emit(tail)
            visible.append(tail)
    return " ".join(visible)

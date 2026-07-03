"""Utilities for turning model output into user-visible answers."""

from __future__ import annotations

import re


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_THINK_BLOCK_RE = re.compile(
    r"<think>.*?</think>|```(?:thinking|reasoning)[\s\S]*?```",
    re.IGNORECASE,
)
_OUTPUT_GENERATION_RE = re.compile(
    r"\[Output Generation\]\s*->\s*[\"“](.+?)[\"”]\s*(?:$|\n)",
    re.IGNORECASE | re.DOTALL,
)
_QUOTED_LONG_RE = re.compile(r"[\"“]([^\"”]{40,})[\"”]", re.DOTALL)


def clean_visible_answer(answer: str) -> str:
    """Remove leaked chain-of-thought style wrappers from a model response."""
    text = _ANSI_RE.sub("", str(answer or "")).strip()
    if not text:
        return ""

    text = _THINK_BLOCK_RE.sub("", text).strip()
    if not text:
        return ""

    lower_head = text[:600].casefold()
    leaked_reasoning = any(
        marker in lower_head
        for marker in (
            "here's a thinking process",
            "here’s a thinking process",
            "here is a thinking process",
            "thinking process:",
            "reasoning process:",
            "self-correction",
            "mental refinement",
            "analyze user input",
        )
    )

    if not leaked_reasoning:
        return text

    for marker in ("Final Answer:", "Final answer:", "Final:", "Antwort:", "Trinity:", "Output:"):
        if marker in text:
            return text.rsplit(marker, 1)[-1].strip()

    output_match = _OUTPUT_GENERATION_RE.search(text)
    if output_match:
        return output_match.group(1).strip()

    quoted = [item.strip() for item in _QUOTED_LONG_RE.findall(text) if item.strip()]
    if quoted:
        return quoted[-1]

    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    return paragraphs[-1] if paragraphs else text

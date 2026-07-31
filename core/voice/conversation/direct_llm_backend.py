"""Diagnostic direct-LLM backend.

This backend intentionally bypasses Trinity's tools, memory and policy layer and
must never be selected by a production profile.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from urllib.request import Request, urlopen

from ..interfaces import ConversationBackend
from ..language_policy import GERMAN_ONLY_PROMPT, enforce_input_language, segment_for_speech


class DirectLLMConversationBackend(ConversationBackend):
    def __init__(self, base_url: str, model: str, api_key: str = "", timeout: int = 120):
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

    def respond(self, text: str, *, session_id: str = "", turn_id: str = "") -> Iterable[str]:
        rejection = enforce_input_language(text)
        if rejection:
            return [rejection]
        payload = json.dumps({
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": GERMAN_ONLY_PROMPT},
                {"role": "user", "content": text},
            ],
        }).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = Request(self.url, data=payload, headers=headers, method="POST")
        with urlopen(request, timeout=self.timeout) as response:  # noqa: S310 - configured local diagnostic endpoint
            data = json.loads(response.read().decode("utf-8"))
        answer = data["choices"][0]["message"]["content"]
        return segment_for_speech(answer)

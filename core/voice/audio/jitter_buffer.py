"""Small bounded jitter buffer for remote PCM chunks."""

from __future__ import annotations

from collections import deque


class JitterBuffer:
    def __init__(self, max_chunks: int = 64):
        self.max_chunks = max(1, int(max_chunks))
        self._chunks: deque[bytes] = deque(maxlen=self.max_chunks)

    def push(self, chunk: bytes) -> None:
        if chunk:
            self._chunks.append(bytes(chunk))

    def pop(self) -> bytes | None:
        return self._chunks.popleft() if self._chunks else None

    def clear(self) -> None:
        self._chunks.clear()

    def __len__(self) -> int:
        return len(self._chunks)

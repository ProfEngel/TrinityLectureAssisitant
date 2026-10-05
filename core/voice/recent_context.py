"""Bound immediate listening context; permanent history is stored separately."""
from collections import deque
import threading
import time


class RecentVoiceContext:
    def __init__(self, max_chars=8000, max_age=180, clock=time.monotonic):
        self.max_chars = max_chars
        self.max_age = max_age
        self.clock = clock
        self.items = deque()
        self.lock = threading.Lock()

    def append(self, role, text):
        now = self.clock()
        text = str(text).strip()[-self.max_chars:]
        with self.lock:
            # Parakeet can deliver a final transcript followed by its extended
            # revision. Replace that context entry rather than repeating it.
            if self.items:
                stamp, old_role, old_text = self.items[-1]
                if old_role == role and now - stamp < 4 and text.startswith(old_text):
                    self.items.pop()
            self.items.append((now, role, text))
            while self.items and (now - self.items[0][0] > self.max_age or
                    sum(len(item[2]) + len(item[1]) + 5 for item in self.items) > self.max_chars):
                self.items.popleft()

    def render(self):
        with self.lock:
            now = self.clock()
            return "\n".join(f"[{role}]: {text}" for stamp, role, text in self.items
                             if now - stamp <= self.max_age)

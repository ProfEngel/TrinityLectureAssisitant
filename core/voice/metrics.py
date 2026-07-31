"""Latency metrics without prompt, transcript, token or secret logging."""

from __future__ import annotations

import json
import statistics
import threading
import time
from collections import defaultdict
from pathlib import Path


class VoiceMetrics:
    def __init__(self, log_path: str | Path | None = None):
        self.log_path = Path(log_path) if log_path else None
        self._values: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def observe(self, name: str, seconds: float, *, session_id: str = "", turn_id: str = "") -> None:
        value = max(0.0, float(seconds))
        with self._lock:
            self._values[name].append(value)
            if self.log_path:
                self.log_path.parent.mkdir(parents=True, exist_ok=True)
                with self.log_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps({
                        "timestamp": time.time(), "metric": name, "seconds": value,
                        "session_id": session_id, "turn_id": turn_id,
                    }, sort_keys=True) + "\n")

    def summary(self) -> dict[str, dict[str, float]]:
        with self._lock:
            result = {}
            for name, values in self._values.items():
                ordered = sorted(values)
                p90_index = max(0, min(len(ordered) - 1, int(len(ordered) * 0.9) - 1))
                result[name] = {
                    "count": float(len(values)),
                    "mean": statistics.fmean(values),
                    "max": max(values),
                    "p90": ordered[p90_index],
                }
            return result

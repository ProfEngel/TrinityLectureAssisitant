"""Silent, read-only model stream probe; no playback or Memory writeback."""
import sys
import time
from pathlib import Path

home = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(home / "core"))
from brain import TrinityBrain

brain = TrinityBrain()
started = time.monotonic()
times = []
def emit(sentence):
    times.append(time.monotonic() - started)
    print(f"sentence={len(times)} seconds={times[-1]:.2f} chars={len(sentence)}", flush=True)

answer, _ = brain.ask(
    "Erkläre in fünf kurzen Sätzen, warum Wasser beim Gefrieren sein Volumen verändert.",
    str(home / "TrinityRuntime/voice/voice_context.md"),
    voice_budget=True, sentence_callback=emit,
)
print(f"completed={time.monotonic() - started:.2f} sentences={len(times)} chars={len(answer)}", flush=True)

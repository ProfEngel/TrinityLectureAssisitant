import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
CORE_DIR = ROOT_DIR / "core"

for path in (ROOT_DIR, CORE_DIR):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)

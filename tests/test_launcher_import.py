import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def test_launcher_imports_from_a_fresh_python_process():
    result = subprocess.run(
        [sys.executable, "-c", "import trinity_launcher"],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode == 0, result.stderr

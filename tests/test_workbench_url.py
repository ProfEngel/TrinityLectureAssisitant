import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "workbench_url", ROOT / "scripts" / "workbench_url.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_uses_enabled_companion_bridge_and_normalizes_bind_host():
    config = {
        "companion": {"enabled": True, "host": "0.0.0.0", "port": 8766},
        "server": {"host": "127.0.0.1", "port": 8765},
    }

    assert MODULE.resolve_workbench_url(config) == "http://127.0.0.1:8766"


def test_uses_server_when_companion_is_disabled():
    config = {
        "companion": {"enabled": False, "host": "0.0.0.0", "port": 8766},
        "server": {"host": "localhost", "port": 9000},
    }

    assert MODULE.resolve_workbench_url(config) == "http://localhost:9000"

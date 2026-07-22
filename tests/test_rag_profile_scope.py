import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rag_agent_rejects_legacy_and_foreign_profiles(tmp_path):
    module = _load_module("trinity_rag_agent_scope", ROOT / "agents/rag_agent/script.py")
    core = tmp_path / "core"
    core.mkdir()
    (core / "config.json").write_text(
        '{"system":{"profile":"PRIVAT"}}',
        encoding="utf-8",
    )

    assert module._configured_profile(str(tmp_path)) == "PRIVAT"
    assert module._index_profile_is_allowed({}, "PRIVAT") is False
    assert module._index_profile_is_allowed({"profile": "BIZ"}, "PRIVAT") is False
    assert module._index_profile_is_allowed({"profile": "PRIVAT"}, "PRIVAT") is True


def test_rag_profile_helper_reads_config_and_has_safe_platform_defaults(tmp_path):
    module = _load_module("trinity_rag_profile_scope", ROOT / "core/rag_profile.py")
    core = tmp_path / "core"
    core.mkdir()
    (core / "config.json").write_text(
        '{"system":{"profile":"BIZ"}}',
        encoding="utf-8",
    )

    assert module.configured_profile(str(tmp_path)) == "BIZ"
    assert module.configured_profile(tmp_path / "missing", platform_name="win32") == "BIZ"
    assert module.configured_profile(tmp_path / "missing", platform_name="darwin") == "PRIVAT"

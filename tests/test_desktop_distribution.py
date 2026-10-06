import importlib.util
import json
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("desktop_first_run", ROOT / "desktop_distribution/first_run.py")
distribution = importlib.util.module_from_spec(spec)
spec.loader.exec_module(distribution)


@pytest.mark.parametrize("source,result", [
    ("http://localhost:1234", "http://localhost:1234/v1/chat/completions"),
    ("https://example.org/api/v1/", "https://example.org/api/v1/chat/completions"),
    ("https://example.org/v1/chat/completions", "https://example.org/v1/chat/completions"),
])
def test_api_url(source, result):
    assert distribution.normalize_api_url(source) == result


@pytest.mark.parametrize("source", ["file:///tmp/api", "http://user:secret@localhost", "https://example.org?token=x", ""])
def test_unsafe_api_url(source):
    with pytest.raises(ValueError):
        distribution.normalize_api_url(source)


@pytest.mark.parametrize("name", ["../private.txt", "/private.txt", "C:/private.txt", "a\\private.txt"])
def test_zip_traversal(tmp_path, name):
    archive = tmp_path / "payload.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(name, "not installed")
    with pytest.raises(ValueError):
        distribution.safe_extract(archive, tmp_path / "app")


def test_fresh_configuration_never_uses_private_credentials(tmp_path, monkeypatch):
    monkeypatch.setattr(distribution, "resources", lambda: tmp_path)
    config = distribution.new_config(ROOT, dict(mode="standalone", url="http://localhost:1234/v1", model="my-model", key="", voice_url=""))
    assert config["llm"]["local"]["api_key"] == ""
    assert not config["canvas"]["enabled"]
    assert not config["client"]["enabled"]
    assert config["voice"]["profiles"][config["voice"]["profile"]]["num_pipelines"] == 1
    assert "CustomVoice" in config["voice"]["profiles"][config["voice"]["profile"]]["tts_model"]


def test_client_configuration_does_not_run_inference(tmp_path, monkeypatch):
    monkeypatch.setattr(distribution, "resources", lambda: tmp_path)
    config = distribution.new_config(ROOT, dict(mode="client", url="https://trinity.example.org", model="", key="example-token", voice_url=""))
    assert config["client"]["enabled"]
    assert config["voice"]["remote_voice_url"] == "wss://trinity.example.org:8766/v1/realtime"
    assert config["voice"]["profile"] == "trinity-mac-client"

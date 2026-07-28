import importlib.util
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "presentation_image", ROOT / "scripts" / "presentation_image.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _args(tmp_path, provider, model):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("Ein didaktisches Schaubild ohne Text.", encoding="utf-8")
    return SimpleNamespace(
        provider=provider,
        model=model,
        prompt_file=str(prompt),
        output=str(tmp_path / "figure.png"),
        aspect_ratio="16:9",
        resolution="2K",
        timeout=30,
    )


def test_kie_generation_reads_key_from_environment_and_writes_output(
    monkeypatch, tmp_path
):
    calls = []

    def fake_request(url, **kwargs):
        calls.append((url, kwargs))
        if url == MODULE.KIE_CREATE_URL:
            return {"code": 200, "data": {"taskId": "task-1"}}
        return {
            "code": 200,
            "data": {
                "state": "success",
                "resultJson": '{"resultUrls":["https://example.invalid/image.png"]}',
            },
        }

    monkeypatch.setenv("KIE_API_KEY", "private-kie-key")
    monkeypatch.setattr(MODULE, "_request_json", fake_request)
    monkeypatch.setattr(
        MODULE,
        "_download",
        lambda url, output: output.write_bytes(b"PNG") or 3,
    )

    result = MODULE.generate(_args(tmp_path, "kie", "nano-banana-2"))

    assert result["ok"] is True
    assert result["provider"] == "kie"
    assert (tmp_path / "figure.png").read_bytes() == b"PNG"
    assert "private-kie-key" not in str(result)
    assert calls[0][1]["headers"]["Authorization"] == "Bearer private-kie-key"


def test_fal_generation_uses_server_side_key_header(monkeypatch, tmp_path):
    captured = {}

    def fake_request(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return {"images": [{"url": "https://example.invalid/fal.png"}]}

    monkeypatch.setenv("FAL_KEY", "private-fal-key")
    monkeypatch.setattr(MODULE, "_request_json", fake_request)
    monkeypatch.setattr(
        MODULE,
        "_download",
        lambda url, output: output.write_bytes(b"PNG") or 3,
    )

    result = MODULE.generate(_args(tmp_path, "fal", "fal-ai/nano-banana-2"))

    assert result["ok"] is True
    assert captured["url"].endswith("/fal-ai/nano-banana-2")
    assert captured["headers"]["Authorization"] == "Key private-fal-key"
    assert "private-fal-key" not in str(result)

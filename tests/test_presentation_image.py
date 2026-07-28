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

    result = MODULE.generate(
        _args(tmp_path, "kie", "gpt-image-2-text-to-image")
    )

    assert result["ok"] is True
    assert result["provider"] == "kie"
    assert (tmp_path / "figure.png").read_bytes() == b"PNG"
    assert "private-kie-key" not in str(result)
    assert calls[0][1]["headers"]["Authorization"] == "Bearer private-kie-key"
    assert calls[0][1]["payload"]["input"] == {
        "prompt": "Ein didaktisches Schaubild ohne Text.",
        "aspect_ratio": "16:9",
    }


def test_kie_model_specific_payloads(monkeypatch):
    captured = []

    def fake_request(url, **kwargs):
        captured.append(kwargs["payload"])
        return {"code": 200, "data": {"taskId": "task-1"}}

    monkeypatch.setattr(MODULE, "_request_json", fake_request)
    monkeypatch.setattr(
        MODULE,
        "time",
        SimpleNamespace(monotonic=lambda: 1000, sleep=lambda _seconds: None),
    )

    for model in ("nano-banana-2-lite", "flux-2/pro-text-to-image"):
        try:
            MODULE._kie_image_url(
                api_key="key",
                model=model,
                prompt="Prompt",
                aspect_ratio="16:9",
                resolution="2K",
                timeout_seconds=0,
            )
        except MODULE.PresentationImageError as exc:
            assert "Zeitlimit" in str(exc)

    lite_input = captured[0]["input"]
    flux_input = captured[1]["input"]
    assert lite_input["image_urls"] == []
    assert "resolution" not in lite_input
    assert flux_input["resolution"] == "2K"
    assert flux_input["nsfw_checker"] is False


def test_fal_provider_is_excluded(monkeypatch, tmp_path):
    monkeypatch.setenv("FAL_KEY", "private-fal-key")

    try:
        MODULE.generate(_args(tmp_path, "fal", "fal-ai/nano-banana-2"))
    except MODULE.PresentationImageError as exc:
        assert str(exc) == "Provider muss kie sein."
    else:
        raise AssertionError("fal.ai darf in der Präsentationswerkstatt nicht laufen.")

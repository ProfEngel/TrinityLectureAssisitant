import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_agent(name):
    path = ROOT / "agents" / name / "script.py"
    spec = importlib.util.spec_from_file_location(f"test_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_plain_image_request_uses_local_comfyui_by_default():
    comfyui = load_agent("comfyui_agent")
    fal = load_agent("image_agent")

    prompt = "Erstelle ein Schaubild zur Spieltheorie."
    assert comfyui.can_handle(prompt) is True
    assert fal.can_handle(prompt) is False


def test_explicit_external_image_request_uses_fal_ai():
    comfyui = load_agent("comfyui_agent")
    fal = load_agent("image_agent")

    prompt = "Erstelle ein externes Bild zur Spieltheorie."
    assert comfyui.can_handle(prompt) is False
    assert fal.can_handle(prompt) is True


def test_explicit_fal_ai_request_never_falls_back_to_local_routing():
    comfyui = load_agent("comfyui_agent")
    fal = load_agent("image_agent")

    prompt = "Generiere die Grafik über fal.ai."
    assert comfyui.can_handle(prompt) is False
    assert fal.can_handle(prompt) is True


def test_external_illustration_wording_also_selects_fal_ai():
    comfyui = load_agent("comfyui_agent")
    fal = load_agent("image_agent")

    prompt = "Erstelle eine externe Illustration zur Spieltheorie."
    assert comfyui.can_handle(prompt) is False
    assert fal.can_handle(prompt) is True
